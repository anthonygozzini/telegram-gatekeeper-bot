"""Configuration: questions and rules come from config.toml; secrets and chat IDs from the environment."""
import os
import tomllib
from dataclasses import dataclass

QUESTION_TYPES = {"social_url", "yes_no", "text"}
PLATFORMS = ("x", "instagram", "tiktok", "youtube", "github", "linkedin")
SIGNAL_NAMES = ("no_username", "many_digits_username", "suspicious_name", "duplicate_profile")
SEVERITIES = {"review", "ignore"}
MODES = {"auto", "manual"}
ENV_VARS = ("TOKEN", "ADMIN_GROUP_ID", "GROUP_CHAT_ID", "LOG_CHANNEL_ID", "DATABASE_PATH", "CONFIG_PATH")

DEFAULT_TEXTS = {
    "welcome": "Welcome! Answer a few questions to request access to the group.",
    "start_button": "Request access",
    "approved": "You're in. Here is your one-time invite link: {link}",
    "rejected": "Sorry, your request was not approved.",
    "in_review": "Thanks! An admin will review your request.",
    "cooldown": "You already applied recently. Please try again later.",
    "invalid": "That answer is not valid: {reason}",
    "not_started": "Send /start to request access.",
}


class ConfigError(ValueError):
    pass


@dataclass(frozen=True)
class Question:
    id: str
    prompt: str
    type: str
    platforms: tuple = ()
    approve_if: str | None = None
    min_length: int = 0


@dataclass(frozen=True)
class Config:
    mode: str
    invite_expire_hours: int
    reapply_cooldown_hours: int
    texts: dict
    questions: tuple
    signals: dict
    suspicious_name_words: tuple


def _positive_int(data, key, default):
    value = data.get(key, default)
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise ConfigError(f"{key} must be a whole number of hours, 0 or more")
    return value


def parse(data: dict) -> Config:
    mode = data.get("mode", "manual")
    if mode not in MODES:
        raise ConfigError(f"mode must be one of {sorted(MODES)}, got {mode!r}")

    texts = dict(DEFAULT_TEXTS)
    for key, value in data.get("texts", {}).items():
        if key not in DEFAULT_TEXTS:
            raise ConfigError(f"unknown text {key!r}; known texts: {sorted(DEFAULT_TEXTS)}")
        if not isinstance(value, str) or not value.strip():
            raise ConfigError(f"text {key!r} must be a non-empty string")
        texts[key] = value

    raw_questions = data.get("questions", [])
    if not raw_questions:
        raise ConfigError("at least one [[questions]] entry is required")
    questions, seen = [], set()
    for raw in raw_questions:
        qid, qtype, prompt = raw.get("id"), raw.get("type"), raw.get("prompt")
        if not qid or not isinstance(qid, str):
            raise ConfigError("every question needs an id")
        if qid in seen:
            raise ConfigError(f"question id {qid!r} is used twice")
        seen.add(qid)
        if qtype not in QUESTION_TYPES:
            raise ConfigError(f"question {qid!r}: type must be one of {sorted(QUESTION_TYPES)}")
        if not prompt or not isinstance(prompt, str):
            raise ConfigError(f"question {qid!r} needs a prompt")
        platforms = tuple(raw.get("platforms", ()))
        if qtype == "social_url":
            if not platforms:
                raise ConfigError(f"question {qid!r}: social_url needs a platforms list")
            unknown = [p for p in platforms if p not in PLATFORMS]
            if unknown:
                raise ConfigError(f"question {qid!r}: unknown platforms {unknown}; supported: {list(PLATFORMS)}")
        elif platforms:
            raise ConfigError(f"question {qid!r}: platforms only applies to social_url questions")
        approve_if = raw.get("approve_if")
        if approve_if is not None and (qtype != "yes_no" or approve_if not in ("yes", "no")):
            raise ConfigError(f"question {qid!r}: approve_if must be \"yes\" or \"no\" on a yes_no question")
        min_length = raw.get("min_length", 0)
        if not isinstance(min_length, int) or min_length < 0 or (min_length and qtype != "text"):
            raise ConfigError(f"question {qid!r}: min_length must be a number 0 or more, on a text question")
        questions.append(Question(qid, prompt, qtype, platforms, approve_if, min_length))

    raw_signals = dict(data.get("signals", {}))
    words = raw_signals.pop("suspicious_name_words", [])
    if not isinstance(words, list) or not all(isinstance(w, str) and w.strip() for w in words):
        raise ConfigError("signals.suspicious_name_words must be a list of words")
    signals = {name: "review" for name in SIGNAL_NAMES}
    for name, severity in raw_signals.items():
        if name not in SIGNAL_NAMES:
            raise ConfigError(f"unknown signal {name!r}; known signals: {list(SIGNAL_NAMES)}")
        if severity not in SEVERITIES:
            raise ConfigError(f"signal {name!r} must be \"review\" or \"ignore\"")
        signals[name] = severity

    return Config(
        mode=mode,
        invite_expire_hours=_positive_int(data, "invite_expire_hours", 24),
        reapply_cooldown_hours=_positive_int(data, "reapply_cooldown_hours", 72),
        texts=texts,
        questions=tuple(questions),
        signals=signals,
        suspicious_name_words=tuple(w.strip().lower() for w in words),
    )


def load(path: str) -> Config:
    try:
        with open(path, "rb") as fh:
            return parse(tomllib.load(fh))
    except FileNotFoundError:
        raise ConfigError(f"config file not found: {path} (copy config.example.toml to start)") from None
    except tomllib.TOMLDecodeError as exc:
        raise ConfigError(f"{path} is not valid TOML: {exc}") from None


@dataclass(frozen=True)
class Env:
    token: str
    admin_group_id: int
    group_chat_id: int
    log_channel_id: int | None
    database_path: str
    config_path: str


def _chat_id(environ, name, required):
    raw = (environ.get(name) or "").strip()
    if not raw:
        if required:
            raise ConfigError(f"{name} is not set (see envexample)")
        return None
    try:
        return int(raw)
    except ValueError:
        raise ConfigError(f"{name} must be a numeric Telegram chat ID, got {raw!r}") from None


def load_env(environ=os.environ) -> Env:
    token = (environ.get("TOKEN") or "").strip()
    if not token:
        raise ConfigError("TOKEN is not set (see envexample)")
    return Env(
        token=token,
        admin_group_id=_chat_id(environ, "ADMIN_GROUP_ID", True),
        group_chat_id=_chat_id(environ, "GROUP_CHAT_ID", True),
        log_channel_id=_chat_id(environ, "LOG_CHANNEL_ID", False),
        database_path=(environ.get("DATABASE_PATH") or "gatekeeper.db").strip(),
        config_path=(environ.get("CONFIG_PATH") or "config.toml").strip(),
    )
