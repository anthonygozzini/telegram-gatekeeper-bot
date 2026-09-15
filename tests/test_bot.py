import inspect
import pathlib
import tomllib
from types import SimpleNamespace

from telegram import Bot, CallbackQuery, Message

from gatekeeper import bot, config

ROOT = pathlib.Path(__file__).resolve().parent.parent


def test_admin_report_escapes_text_and_links_profiles():
    cfg = config.parse(tomllib.loads((ROOT / "config.example.toml").read_text(encoding="utf-8")))
    user = SimpleNamespace(id=42, full_name="<Mario>", username=None)
    answers = {"profile": "x:mario", "rules": "yes", "why": "I like <b>tags</b>"}
    text = bot.admin_report(7, user, answers, [("no_username", "no Telegram username")], cfg, "waiting for an admin")
    assert "&lt;Mario&gt;" in text and "&lt;b&gt;tags" in text
    assert 'href="https://x.com/mario"' in text
    assert "• no Telegram username" in text


def test_telegram_calls_use_parameters_that_exist():
    assert {"chat_id", "text", "parse_mode", "reply_markup", "link_preview_options"} <= set(inspect.signature(Bot.send_message).parameters)
    assert {"chat_id", "member_limit", "expire_date", "name"} <= set(inspect.signature(Bot.create_chat_invite_link).parameters)
    assert {"text", "parse_mode", "link_preview_options"} <= set(inspect.signature(CallbackQuery.edit_message_text).parameters)
    assert {"text", "reply_markup"} <= set(inspect.signature(Message.reply_text).parameters)
    assert hasattr(Message, "text_html")
