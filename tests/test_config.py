import pathlib
import tomllib

import pytest

from gatekeeper import config

ROOT = pathlib.Path(__file__).resolve().parent.parent


def example():
    return tomllib.loads((ROOT / "config.example.toml").read_text(encoding="utf-8"))


def test_example_config_is_valid():
    cfg = config.parse(example())
    assert cfg.mode == "auto"
    assert [q.id for q in cfg.questions] == ["profile", "rules", "why"]
    assert cfg.signals["duplicate_profile"] == "review"
    assert "support" in cfg.suspicious_name_words


@pytest.mark.parametrize("change, message", [
    (lambda d: d.update(mode="sometimes"), "mode must be"),
    (lambda d: d["questions"][0].update(type="date"), "type must be"),
    (lambda d: d["questions"][1].update(id="profile"), "used twice"),
    (lambda d: d["questions"][0].pop("platforms"), "needs a platforms list"),
    (lambda d: d["questions"][2].update(approve_if="yes"), "approve_if must be"),
    (lambda d: d["signals"].update(bad_thing="review"), "unknown signal"),
    (lambda d: d["texts"].update(hello="hi"), "unknown text"),
    (lambda d: d.update(questions=[]), "at least one"),
    (lambda d: d.update(invite_expire_hours=-1), "whole number"),
])
def test_invalid_configs_are_explained(change, message):
    data = example()
    change(data)
    with pytest.raises(config.ConfigError, match=message):
        config.parse(data)


def test_env_requires_token_and_numeric_ids():
    with pytest.raises(config.ConfigError, match="TOKEN is not set"):
        config.load_env({})
    with pytest.raises(config.ConfigError, match="must be a numeric"):
        config.load_env({"TOKEN": "t", "ADMIN_GROUP_ID": "abc", "GROUP_CHAT_ID": "-1002"})


def test_env_defaults():
    env = config.load_env({"TOKEN": "t", "ADMIN_GROUP_ID": "-1001", "GROUP_CHAT_ID": "-1002", "LOG_CHANNEL_ID": ""})
    assert (env.admin_group_id, env.group_chat_id, env.log_channel_id) == (-1001, -1002, None)
    assert (env.database_path, env.config_path) == ("gatekeeper.db", "config.toml")


def test_every_environment_variable_is_documented():
    documented = {line.split("=")[0] for line in (ROOT / "envexample").read_text().splitlines() if "=" in line and not line.startswith("#")}
    assert set(config.ENV_VARS) <= documented
