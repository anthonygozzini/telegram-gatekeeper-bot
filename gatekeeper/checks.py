"""Pure rules: answer validation, anti-farm signals and the approval decision. No Telegram, no I/O."""
import re

_PROFILE_PATTERNS = {
    "x": re.compile(r"^(?:https?://)?(?:www\.|mobile\.)?(?:twitter\.com|x\.com)/([A-Za-z0-9_]{1,15})/?(?:[?#].*)?$", re.I),
    "instagram": re.compile(r"^(?:https?://)?(?:www\.)?instagram\.com/([A-Za-z0-9_.]{1,30})/?(?:[?#].*)?$", re.I),
    "tiktok": re.compile(r"^(?:https?://)?(?:www\.)?tiktok\.com/@([A-Za-z0-9_.]{2,24})/?(?:[?#].*)?$", re.I),
    "youtube": re.compile(r"^(?:https?://)?(?:www\.|m\.)?youtube\.com/(@[A-Za-z0-9_.-]{3,30}|channel/UC[A-Za-z0-9_-]{22})/?(?:[?#].*)?$", re.I),
    "github": re.compile(r"^(?:https?://)?(?:www\.)?github\.com/([A-Za-z0-9](?:[A-Za-z0-9-]{0,37}[A-Za-z0-9])?)/?(?:[?#].*)?$", re.I),
    "linkedin": re.compile(r"^(?:https?://)?(?:[a-z]{2,3}\.)?linkedin\.com/in/([A-Za-z0-9_%-]{3,100})/?(?:[?#].*)?$", re.I),
}
# Paths on these sites that look like a profile handle but are pages of the site itself.
_RESERVED = {
    "x": {"home", "i", "search", "explore", "intent", "share", "settings", "messages", "notifications", "hashtag", "login"},
    "instagram": {"p", "reel", "reels", "explore", "stories", "accounts", "direct"},
    "github": {"orgs", "topics", "features", "settings", "marketplace", "explore", "login", "about", "pricing"},
}
_PROFILE_URLS = {
    "x": "https://x.com/{}",
    "instagram": "https://www.instagram.com/{}/",
    "tiktok": "https://www.tiktok.com/@{}",
    "youtube": "https://www.youtube.com/{}",
    "github": "https://github.com/{}",
    "linkedin": "https://www.linkedin.com/in/{}",
}
_PLATFORM_NAMES = {"x": "X", "instagram": "Instagram", "tiktok": "TikTok", "youtube": "YouTube", "github": "GitHub", "linkedin": "LinkedIn"}
YES = {"yes", "y", "si", "sì"}
NO = {"no", "n"}


def check_social_url(text, platforms):
    """Return (profile_key, None) for a valid profile link, or (None, reason)."""
    candidate = text.strip()
    for platform in platforms:
        match = _PROFILE_PATTERNS[platform].match(candidate)
        if match:
            handle = match.group(1)
            if handle.lower() in _RESERVED.get(platform, set()):
                return None, "that link is not a profile"
            # YouTube channel IDs are case-sensitive; every other handle is not.
            key = handle if platform == "youtube" and handle.lower().startswith("channel/") else handle.lower()
            return f"{platform}:{key}", None
    names = ", ".join(_PLATFORM_NAMES[p] for p in platforms)
    return None, f"send the link to a profile on {names}"


def profile_url(profile_key):
    platform, handle = profile_key.split(":", 1)
    return _PROFILE_URLS[platform].format(handle)


def check_answer(question, text):
    """Return (value, None) or (None, reason). social_url answers are returned as profile keys."""
    if question.type == "social_url":
        return check_social_url(text, question.platforms)
    if question.type == "yes_no":
        word = text.strip().lower()
        if word in YES:
            return "yes", None
        if word in NO:
            return "no", None
        return None, "please answer yes or no"
    answer = text.strip()
    if len(answer) < question.min_length:
        return None, f"please write at least {question.min_length} characters"
    return answer, None


def find_signals(username, first_name, last_name, duplicate_profiles, suspicious_words):
    """Signals worth a human look. They never reject anyone on their own."""
    found = []
    if not username:
        found.append(("no_username", "no Telegram username"))
    elif sum(ch.isdigit() for ch in username) >= 5:
        found.append(("many_digits_username", f"@{username} contains many digits"))
    name = " ".join(part for part in (first_name, last_name, username) if part).lower()
    hits = [word for word in suspicious_words if word in name]
    if hits:
        found.append(("suspicious_name", "name contains " + ", ".join(hits)))
    for key in duplicate_profiles:
        found.append(("duplicate_profile", f"{key} is already used by another applicant"))
    return found


def decide(mode, questions, answers, signals, severities):
    """"approve", "reject" or "review" (an admin decides)."""
    if mode == "manual":
        return "review"
    for question in questions:
        if question.type == "yes_no" and question.approve_if and answers.get(question.id) != question.approve_if:
            return "reject"
    if any(severities.get(code) == "review" for code, _ in signals):
        return "review"
    return "approve"
