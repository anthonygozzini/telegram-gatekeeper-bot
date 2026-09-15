import pytest

from gatekeeper import checks
from gatekeeper.config import Question

ALL = ("x", "instagram", "tiktok", "youtube", "github", "linkedin")
SOCIAL = Question("profile", "Send your profile", "social_url", ALL)


@pytest.mark.parametrize("link, key", [
    ("https://x.com/Jack", "x:jack"),
    ("twitter.com/jack?s=20", "x:jack"),
    ("https://www.instagram.com/some.user/", "instagram:some.user"),
    ("https://www.tiktok.com/@user_1", "tiktok:user_1"),
    ("https://youtube.com/@MyChannel", "youtube:@mychannel"),
    ("https://www.youtube.com/channel/UC1234567890abcdefghijKL", "youtube:channel/UC1234567890abcdefghijKL"),
    ("github.com/octo-cat", "github:octo-cat"),
    ("https://it.linkedin.com/in/mario-rossi-123", "linkedin:mario-rossi-123"),
])
def test_valid_profiles(link, key):
    assert checks.check_answer(SOCIAL, link) == (key, None)


@pytest.mark.parametrize("link", ["https://x.com/home", "https://www.instagram.com/p/", "https://github.com/settings"])
def test_site_pages_are_not_profiles(link):
    assert checks.check_answer(SOCIAL, link) == (None, "that link is not a profile")


def test_platform_not_allowed():
    only_x = Question("profile", "p", "social_url", ("x",))
    value, reason = checks.check_answer(only_x, "https://www.instagram.com/someone/")
    assert value is None and "X" in reason


def test_profile_url_round_trip():
    assert checks.profile_url("x:jack") == "https://x.com/jack"
    assert checks.profile_url("youtube:channel/UC1234567890abcdefghijKL") == "https://www.youtube.com/channel/UC1234567890abcdefghijKL"


@pytest.mark.parametrize("text, value", [("Yes", "yes"), ("sì", "yes"), ("N", "no"), (" no ", "no")])
def test_yes_no(text, value):
    assert checks.check_answer(Question("q", "p", "yes_no"), text) == (value, None)


def test_yes_no_rejects_other_words():
    assert checks.check_answer(Question("q", "p", "yes_no"), "maybe")[0] is None


def test_text_min_length():
    question = Question("why", "p", "text", min_length=15)
    assert checks.check_answer(question, "short")[0] is None
    assert checks.check_answer(question, "  I want to learn from the group  ") == ("I want to learn from the group", None)


def test_signals():
    assert [code for code, _ in checks.find_signals(None, "Mario", None, [], [])] == ["no_username"]
    assert [code for code, _ in checks.find_signals("user12345", "Mario", None, [], [])] == ["many_digits_username"]
    codes = [code for code, _ in checks.find_signals("mario", "Crypto", "Support", ["x:jack"], ["support", "admin"])]
    assert codes == ["suspicious_name", "duplicate_profile"]


QUESTIONS = (SOCIAL, Question("rules", "p", "yes_no", approve_if="yes"))
REVIEW_ALL = {"no_username": "review"}


def test_decide_manual_always_reviews():
    assert checks.decide("manual", QUESTIONS, {"rules": "yes"}, [], REVIEW_ALL) == "review"


def test_decide_auto():
    assert checks.decide("auto", QUESTIONS, {"rules": "yes"}, [], REVIEW_ALL) == "approve"
    assert checks.decide("auto", QUESTIONS, {"rules": "no"}, [], REVIEW_ALL) == "reject"
    assert checks.decide("auto", QUESTIONS, {"rules": "yes"}, [("no_username", "x")], REVIEW_ALL) == "review"
    assert checks.decide("auto", QUESTIONS, {"rules": "yes"}, [("no_username", "x")], {"no_username": "ignore"}) == "approve"
