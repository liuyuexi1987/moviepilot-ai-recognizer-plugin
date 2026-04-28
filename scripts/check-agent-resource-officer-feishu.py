#!/usr/bin/env python3
import importlib.util
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "AgentResourceOfficer" / "feishu_channel.py"
CORE_PATH = ROOT / "AgentResourceOfficer" / "__init__.py"
FORM_PATHS = [
    ROOT / "AgentResourceOfficer" / "__init__.py",
    ROOT / "plugins" / "agentresourceofficer" / "__init__.py",
    ROOT / "plugins.v2" / "agentresourceofficer" / "__init__.py",
]


class FakePlugin:
    def get_config(self):
        return {}

    def get_state(self):
        return True

    @staticmethod
    def _extract_first_url(text):
        match = re.search(r"https?://\S+", str(text or ""))
        return match.group(0) if match else ""

    @staticmethod
    def _is_115_url(url):
        return "115cdn.com" in str(url or "")

    @staticmethod
    def _is_quark_url(url):
        return "pan.quark.cn" in str(url or "")


def load_channel_class():
    spec = importlib.util.spec_from_file_location("agent_resource_officer_feishu_channel", MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.FeishuChannel


def check(name, condition):
    if not condition:
        raise AssertionError(name)


def main():
    channel_cls = load_channel_class()
    channel = channel_cls(FakePlugin())
    channel.configure({})
    default_whitelist = set(channel_cls.default_command_whitelist())
    default_alias_targets = set(channel_cls.parse_alias_text(channel_cls.default_command_aliases()).values())
    missing_alias_targets = sorted(default_alias_targets - default_whitelist)
    check("all default alias targets are whitelisted", not missing_alias_targets)

    cases = {
        "yc蜘蛛侠": "/smart_entry 蜘蛛侠",
        "2蜘蛛侠": "/smart_entry 蜘蛛侠",
        "ps大君夫人": "/pansou_search 大君夫人",
        "1大君夫人": "/pansou_search 大君夫人",
        "选择 1 path=/飞书": "/smart_pick 1 path=/飞书",
        "详情": "/smart_pick 详情",
        "审查": "/smart_pick 审查",
        "n 下一页": "/smart_pick n 下一页",
        "https://pan.quark.cn/s/xxxx": "/smart_entry https://pan.quark.cn/s/xxxx",
        "链接 https://115cdn.com/s/xxxx path=/待整理": "/smart_entry 链接 https://115cdn.com/s/xxxx path=/待整理",
    }
    for raw, expected in cases.items():
        check(f"map {raw}", channel._map_text_to_command(raw) == expected)

    health = channel.health()
    check("health has legacy_bridge_running", "legacy_bridge_running" in health)
    check("health has conflict_warning", "conflict_warning" in health)
    check("health has safe_to_enable", "safe_to_enable" in health)
    check("health has recommended_action", "recommended_action" in health)
    check("health has migration_hint", "migration_hint" in health)
    check("default conflict false", health["conflict_warning"] is False)

    channel.configure({"feishu_enabled": True})
    channel.is_legacy_bridge_running = lambda: True
    health = channel.health()
    check("conflict true when both enabled", health["legacy_bridge_running"] is True and health["conflict_warning"] is True)
    check("conflict recommends disabling legacy", health["recommended_action"] == "disable_legacy_bridge_or_use_different_app")

    required_form_models = [
        '"model": "feishu_reply_receive_id_type"',
        '"model": "feishu_command_whitelist"',
        '"model": "feishu_command_aliases"',
    ]
    for path in FORM_PATHS:
        text = path.read_text(encoding="utf-8")
        for needle in required_form_models:
            check(f"{path.relative_to(ROOT)} has {needle}", needle in text)

    core_text = CORE_PATH.read_text(encoding="utf-8")
    for needle in [
        '("MP搜索", "mp")',
        '("原生搜索", "mp")',
        'if mode == "mp":',
        '"action": "media_search"',
    ]:
        check(f"core assistant route supports {needle}", needle in core_text)

    print("agent_resource_officer_feishu_channel_check_ok")


if __name__ == "__main__":
    main()
