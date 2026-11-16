"""ruleSet expansion in Happ JSON (Xray) routing rules."""

import asyncio
import json

import pytest

from src.happ_processor import process_happ_json
from src.processor import ListFetchError
from src.xray_rules import expand_rules, lines_to_matchers, resolve_rule_sets

LIST_A = "https://lists.example.net/a.list"
LIST_B = "https://lists.example.net/b.list"

LINES = {
    LIST_A: [
        "# RULE-SET,https://lists.example.net/a.list",
        "DOMAIN-SUFFIX,Example.com",
        "DOMAIN,api.example.org",
        "DOMAIN-KEYWORD,examp",
        "IP-CIDR,192.0.2.0/24",
        "IP-CIDR,2001:db8::/32",
        "IP-ASN,64496",
    ],
    LIST_B: ["DOMAIN-SUFFIX,example.com", "DOMAIN-SUFFIX,example.net"],
}


async def fetch(url: str) -> list[str]:
    return LINES[url]


def test_lines_to_matchers():
    domains, ips, skipped = lines_to_matchers(LINES[LIST_A])
    assert domains == ["domain:example.com", "full:api.example.org", "keyword:examp"]
    assert ips == ["192.0.2.0/24", "2001:db8::/32"]
    assert skipped == ["IP-ASN"]


def test_rule_splits_into_domain_and_ip_rules():
    """Xray ANDs matchers inside a rule: domains and ranges must not share one."""
    skeleton = {
        "routing": {
            "rules": [
                {"ip": ["10.0.0.0/8"], "outboundTag": "direct"},
                {
                    "ruleSet": [LIST_A, LIST_B],
                    "network": "tcp,udp",
                    "balancerTag": "PROXY",
                },
                {"network": "tcp,udp", "outboundTag": "direct"},
            ]
        }
    }
    out = asyncio.run(resolve_rule_sets(skeleton, fetch))
    rules = out["routing"]["rules"]
    assert rules[0] == {"ip": ["10.0.0.0/8"], "outboundTag": "direct"}
    assert rules[1] == {
        "network": "tcp,udp",
        "balancerTag": "PROXY",
        "domain": [
            "domain:example.com",
            "full:api.example.org",
            "keyword:examp",
            "domain:example.net",
        ],
    }
    assert rules[2] == {
        "network": "tcp,udp",
        "balancerTag": "PROXY",
        "ip": ["192.0.2.0/24", "2001:db8::/32"],
    }
    assert rules[3] == {"network": "tcp,udp", "outboundTag": "direct"}
    assert "ruleSet" in skeleton["routing"]["rules"][1]  # input untouched


def test_rule_keeps_its_own_matchers():
    skeleton = {
        "routing": {
            "rules": [
                {
                    "ruleSet": [LIST_B],
                    "domain": ["domain:extra.example"],
                    "outboundTag": "block",
                }
            ]
        }
    }
    out = asyncio.run(resolve_rule_sets(skeleton, fetch))
    assert out["routing"]["rules"] == [
        {
            "outboundTag": "block",
            "domain": [
                "domain:extra.example",
                "domain:example.com",
                "domain:example.net",
            ],
        }
    ]


def test_empty_list_drops_the_rule():
    """A rule left with no matcher would match everything — it must vanish instead."""
    skeleton = {"routing": {"rules": [{"ruleSet": [LIST_A], "outboundTag": "block"}]}}
    assert expand_rules(skeleton, {LIST_A: ([], [])})["routing"]["rules"] == []


def test_skeleton_without_rule_sets_is_returned_as_is():
    skeleton = {"routing": {"rules": [{"outboundTag": "direct"}]}}
    assert expand_rules(skeleton, {}) is skeleton


def test_each_list_is_fetched_once():
    calls: list[str] = []

    async def counting(url: str) -> list[str]:
        calls.append(url)
        return LINES[url]

    skeleton = {
        "routing": {
            "rules": [
                {"ruleSet": [LIST_B], "network": "udp", "outboundTag": "block"},
                {"ruleSet": [LIST_B], "balancerTag": "PROXY"},
            ]
        }
    }
    asyncio.run(resolve_rule_sets(skeleton, counting))
    assert calls == [LIST_B]


def test_list_fetch_failure_fails_the_subscription():
    class FailingProcessor:
        async def expand_rule_set(self, task, host, headers):
            raise ListFetchError(task["url"], "boom")

    tpl = "#HAPP,JSON\n" + json.dumps(
        {"routing": {"rules": [{"ruleSet": [LIST_A], "balancerTag": "PROXY"}]}}
    )
    with pytest.raises(ListFetchError):
        asyncio.run(process_happ_json(tpl, None, {}, FailingProcessor()))


def test_process_happ_json_expands_lists_before_building():
    class Processor:
        async def expand_rule_set(self, task, host, headers):
            assert task == {"url": LIST_B, "suffix": ""}
            return LINES[LIST_B]

    tpl = "#HAPP,JSON\n" + json.dumps(
        {
            "outbounds": ["PROXY_OUTBOUNDS"],
            "routing": {"rules": [{"ruleSet": [LIST_B], "balancerTag": "PROXY"}]},
        }
    )
    # no proxy_config → empty subscription, but the expansion still ran (assert above)
    body, _ = asyncio.run(process_happ_json(tpl, None, {}, Processor()))
    assert json.loads(body) == []
