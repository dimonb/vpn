"""RULE-SET lists inside Happ JSON (Xray) routing rules.

A skeleton routing rule may carry ``"ruleSet": [<list url>, ...]``. cfgapp fetches those lists
the way it does for Shadowrocket/Clash templates (cache, NETSET expansion) and replaces the
rule with plain Xray rules:

- one rule with the lists' domains in ``domain`` and one with their ranges in ``ip`` — Xray
  ANDs the matchers inside one rule, so a domain and a range never share a rule;
- every other field of the rule (``network``, ``port``, ``outboundTag``/``balancerTag``…) is
  copied to both, together with any ``domain``/``ip`` the rule already had.

Rule types with no Xray equivalent (``IP-ASN``, ``USER-AGENT``, ``GEOIP``…) are dropped and
logged — a list should carry the ranges as NETSET too if Xray clients need them.
"""

import asyncio
import logging
from collections.abc import Awaitable, Callable
from typing import Any

logger = logging.getLogger(__name__)

RULE_SET_KEY = "ruleSet"

DOMAIN_PREFIXES = {
    "DOMAIN-SUFFIX": "domain:",
    "DOMAIN": "full:",
    "DOMAIN-KEYWORD": "keyword:",
}
IP_TYPES = {"IP-CIDR", "IP-CIDR6"}


def lines_to_matchers(lines: list[str]) -> tuple[list[str], list[str], list[str]]:
    """Shadowrocket rule lines → (Xray domain matchers, ip ranges, skipped rule types)."""
    domains: list[str] = []
    ips: list[str] = []
    skipped: list[str] = []
    for raw in lines:
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        parts = [p.strip() for p in line.split(",")]
        if len(parts) < 2 or not parts[1]:
            continue
        kind, value = parts[0].upper(), parts[1]
        if kind in DOMAIN_PREFIXES:
            domains.append(DOMAIN_PREFIXES[kind] + value.lower())
        elif kind in IP_TYPES:
            ips.append(value)
        else:
            skipped.append(kind)
    return _unique(domains), _unique(ips), skipped


def _unique(items: list[str]) -> list[str]:
    return list(dict.fromkeys(items))


def rule_set_urls(skeleton: dict[str, Any]) -> list[str]:
    """Every list URL the skeleton's routing rules reference, in first-seen order."""
    urls: list[str] = []
    for rule in skeleton.get("routing", {}).get("rules", []):
        if isinstance(rule, dict):
            urls.extend(rule.get(RULE_SET_KEY, []))
    return _unique(urls)


def expand_rules(
    skeleton: dict[str, Any], lists: dict[str, tuple[list[str], list[str]]]
) -> dict[str, Any]:
    """Copy of the skeleton with each ``ruleSet`` rule replaced by domain/ip rules.

    ``lists`` maps a list URL to its (domains, ips). A rule whose lists come out empty
    disappears rather than turning into a rule with no matcher (which matches everything).
    """
    routing = skeleton.get("routing")
    if not routing or not any(
        isinstance(r, dict) and RULE_SET_KEY in r for r in routing.get("rules", [])
    ):
        return skeleton
    rules: list[Any] = []
    for rule in routing.get("rules", []):
        if not isinstance(rule, dict) or RULE_SET_KEY not in rule:
            rules.append(rule)
            continue
        base = {
            k: v for k, v in rule.items() if k not in (RULE_SET_KEY, "domain", "ip")
        }
        domains = list(rule.get("domain", []))
        ips = list(rule.get("ip", []))
        for url in rule[RULE_SET_KEY]:
            list_domains, list_ips = lists[url]
            domains.extend(list_domains)
            ips.extend(list_ips)
        if domains:
            rules.append({**base, "domain": _unique(domains)})
        if ips:
            rules.append({**base, "ip": _unique(ips)})
    return {**skeleton, "routing": {**routing, "rules": rules}}


async def resolve_rule_sets(
    skeleton: dict[str, Any], fetch_lines: Callable[[str], Awaitable[list[str]]]
) -> dict[str, Any]:
    """Fetch every referenced list with ``fetch_lines`` and expand the rules.

    A failed fetch propagates (ListFetchError): a config with a list silently missing would
    send that list's sites the wrong way.
    """
    urls = rule_set_urls(skeleton)
    fetched = await asyncio.gather(*(fetch_lines(url) for url in urls))
    lists: dict[str, tuple[list[str], list[str]]] = {}
    for url, lines in zip(urls, fetched, strict=True):
        domains, ips, skipped = lines_to_matchers(lines)
        if skipped:
            logger.warning(
                f"HAPP JSON: {url}: no Xray equivalent, dropped {sorted(set(skipped))}"
            )
        lists[url] = (domains, ips)
    return expand_rules(skeleton, lists)
