"""Telegram handlers. All rules live in checks.py; this file only moves messages around."""
import html
import logging
import time
from datetime import datetime, timedelta, timezone

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, LinkPreviewOptions, Message, Update
from telegram.constants import ParseMode
from telegram.error import TelegramError
from telegram.ext import Application, CallbackQueryHandler, CommandHandler, ContextTypes, MessageHandler, filters

from . import checks

log = logging.getLogger("gatekeeper")
NO_PREVIEW = LinkPreviewOptions(is_disabled=True)

DECISION_LABELS = {"approve": "approved automatically", "reject": "rejected automatically", "review": "waiting for an admin"}


def build_application(cfg, env, store):
    app = Application.builder().token(env.token).build()
    app.bot_data.update(cfg=cfg, env=env, store=store)
    private = filters.ChatType.PRIVATE
    app.add_handler(CommandHandler("start", start, filters=private))
    app.add_handler(CallbackQueryHandler(begin, pattern=r"^begin$"))
    app.add_handler(CallbackQueryHandler(admin_decision, pattern=r"^(approve|reject):\d+$"))
    app.add_handler(MessageHandler(private & filters.TEXT & ~filters.COMMAND, answer))
    if env.log_channel_id is not None:
        group = filters.Chat(chat_id=env.group_chat_id)
        app.add_handler(MessageHandler(group & filters.StatusUpdate.NEW_CHAT_MEMBERS, member_joined))
        app.add_handler(MessageHandler(group & filters.StatusUpdate.LEFT_CHAT_MEMBER, member_left))
    app.add_error_handler(on_error)
    return app


def _deps(context):
    data = context.application.bot_data
    return data["cfg"], data["env"], data["store"]


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    cfg, _, store = _deps(context)
    last = store.last_application_time(update.effective_user.id)
    if last is not None and time.time() - last < cfg.reapply_cooldown_hours * 3600:
        await update.message.reply_text(cfg.texts["cooldown"])
        return
    context.user_data.clear()
    button = InlineKeyboardMarkup([[InlineKeyboardButton(cfg.texts["start_button"], callback_data="begin")]])
    await update.message.reply_text(cfg.texts["welcome"], reply_markup=button)


async def begin(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    cfg, _, _ = _deps(context)
    query = update.callback_query
    await query.answer()
    context.user_data.clear()
    context.user_data.update(step=0, answers={}, profiles=[])
    await context.bot.send_message(chat_id=query.from_user.id, text=cfg.questions[0].prompt)


async def answer(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    cfg, _, _ = _deps(context)
    state = context.user_data
    if "step" not in state:
        await update.message.reply_text(cfg.texts["not_started"])
        return
    question = cfg.questions[state["step"]]
    value, reason = checks.check_answer(question, update.message.text)
    if reason:
        await update.message.reply_text(cfg.texts["invalid"].format(reason=reason))
        return
    state["answers"][question.id] = value
    if question.type == "social_url":
        state["profiles"].append(value)
    state["step"] += 1
    if state["step"] < len(cfg.questions):
        await update.message.reply_text(cfg.questions[state["step"]].prompt)
        return
    await finish(update, context)


async def finish(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    cfg, env, store = _deps(context)
    user = update.effective_user
    answers, profiles = context.user_data["answers"], context.user_data["profiles"]
    context.user_data.clear()
    duplicates = store.profiles_used_by_others(profiles, user.id)
    signals = checks.find_signals(user.username, user.first_name, user.last_name, duplicates, cfg.suspicious_name_words)
    decision = checks.decide(cfg.mode, cfg.questions, answers, signals, cfg.signals)
    application_id = store.add_application(user.id, user.username, user.full_name, answers, signals, profiles, decision)

    if decision == "approve":
        link = await create_invite(context, application_id)
        store.set_invite_link(application_id, link)
        await update.message.reply_text(cfg.texts["approved"].format(link=link))
    elif decision == "reject":
        await update.message.reply_text(cfg.texts["rejected"])
    else:
        await update.message.reply_text(cfg.texts["in_review"])

    buttons = None
    if decision == "review":
        buttons = InlineKeyboardMarkup([[
            InlineKeyboardButton("Approve", callback_data=f"approve:{application_id}"),
            InlineKeyboardButton("Reject", callback_data=f"reject:{application_id}"),
        ]])
    await context.bot.send_message(
        chat_id=env.admin_group_id,
        text=admin_report(application_id, user, answers, signals, cfg, DECISION_LABELS[decision]),
        parse_mode=ParseMode.HTML,
        reply_markup=buttons,
        link_preview_options=NO_PREVIEW,
    )


async def admin_decision(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    cfg, env, store = _deps(context)
    query = update.callback_query
    if update.effective_chat is None or update.effective_chat.id != env.admin_group_id:
        await query.answer("Decisions can only be taken in the admin group.", show_alert=True)
        return
    action, raw_id = query.data.split(":")
    application_id = int(raw_id)
    admin = query.from_user.username and f"@{query.from_user.username}" or query.from_user.full_name
    decision = "approved" if action == "approve" else "rejected"
    if not store.claim_review(application_id, decision, admin):
        await query.answer("This request was already decided.", show_alert=True)
        return
    await query.answer()
    application = store.get_application(application_id)
    try:
        if decision == "approved":
            link = await create_invite(context, application_id)
            store.set_invite_link(application_id, link)
            await context.bot.send_message(chat_id=application["user_id"], text=cfg.texts["approved"].format(link=link))
        else:
            await context.bot.send_message(chat_id=application["user_id"], text=cfg.texts["rejected"])
    except TelegramError as exc:
        log.warning("could not notify user %s about request #%s: %s", application["user_id"], application_id, exc)
    if isinstance(query.message, Message):
        await query.edit_message_text(
            text=f"{query.message.text_html}\n\n<b>Decision:</b> {decision} by {html.escape(admin)}",
            parse_mode=ParseMode.HTML,
            link_preview_options=NO_PREVIEW,
        )


async def create_invite(context, application_id):
    cfg, env, _ = _deps(context)
    expire = datetime.now(timezone.utc) + timedelta(hours=cfg.invite_expire_hours) if cfg.invite_expire_hours else None
    invite = await context.bot.create_chat_invite_link(
        chat_id=env.group_chat_id, member_limit=1, expire_date=expire, name=f"request #{application_id}"
    )
    return invite.invite_link


def admin_report(application_id, user, answers, signals, cfg, status):
    e = html.escape
    who = f'<a href="tg://user?id={user.id}">{e(user.full_name)}</a>'
    handle = f"@{e(user.username)}" if user.username else "no username"
    lines = [f"<b>Access request #{application_id}</b>", f"{who} · {handle} · id {user.id}", ""]
    for question in cfg.questions:
        value = answers.get(question.id, "")
        if question.type == "social_url" and value:
            shown = f'<a href="{e(checks.profile_url(value))}">{e(value)}</a>'
        else:
            shown = e(str(value))
        lines.append(f"<b>{e(question.id)}:</b> {shown}")
    lines.append("")
    lines.append("<b>Signals:</b> " + ("none" if not signals else ""))
    lines.extend(f"• {e(detail)}" for _, detail in signals)
    lines.append(f"<b>Status:</b> {e(status)}")
    return "\n".join(lines)


async def _member_event(update, context, member, action):
    _, env, store = _deps(context)
    store.add_member_event(member.id, member.username, member.full_name, action, update.effective_chat.id)
    handle = f"@{html.escape(member.username)}" if member.username else "no username"
    text = f'<b>{action.capitalize()}</b>: <a href="tg://user?id={member.id}">{html.escape(member.full_name)}</a> · {handle} · id {member.id}'
    await context.bot.send_message(chat_id=env.log_channel_id, text=text, parse_mode=ParseMode.HTML)


async def member_joined(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    for member in update.message.new_chat_members:
        await _member_event(update, context, member, "joined")


async def member_left(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await _member_event(update, context, update.message.left_chat_member, "left")


async def on_error(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    log.error("error while handling an update", exc_info=context.error)
