"""Full Xray JSON client configs (Happ "JSON subscriptions") with ordered failover.

A Happ subscription whose body is a JSON array hands each element to its Xray core as is,
so the profile can use what share links cannot: an observatory and balancers. The servers of
a subscription group become one config that prefers them in the group's order — the first
while its health checks pass, else the second, and so on, the last taking whatever is left —
plus one config per server for picking it by hand.

Strict order is a chain of one-member ``leastPing`` balancers: each picks its server while
the observatory reports it alive and otherwise falls back (``fallbackTag``) to a loopback
outbound whose traffic re-enters routing at the next balancer. (``leastLoad`` would sort by
RTT deviation, not by order, and a ``fallbackTag`` cannot name a balancer directly.)
"""

import copy
import logging
from typing import Any

logger = logging.getLogger(__name__)

# Placeholders a template uses inside its JSON skeleton.
OUTBOUNDS_PLACEHOLDER = "PROXY_OUTBOUNDS"  # an item of "outbounds"
ROUTE_PLACEHOLDER = "PROXY"  # "balancerTag"/"outboundTag" of a routing rule

TAG_PREFIX = "proxy-"
BALANCER_PREFIX = "failover-"
LOOPBACK_PREFIX = "to-failover-"


def to_xray_outbound(config: dict[str, Any], tag: str) -> dict[str, Any] | None:
    """Xray outbound for a proxy dict from ProxyConfig.generate_proxy_configs (mihomo shape).

    VLESS only (REALITY over TCP, XHTTP over TLS); other protocols return None.
    """
    if config.get("type") != "vless":
        return None
    user: dict[str, Any] = {
        "id": config["uuid"],
        "encryption": config.get("encryption") or "none",
    }
    if config.get("flow"):
        user["flow"] = config["flow"]
    outbound: dict[str, Any] = {
        "tag": tag,
        "protocol": "vless",
        "settings": {
            "vnext": [
                {"address": config["server"], "port": config["port"], "users": [user]}
            ]
        },
    }
    fingerprint = config.get("client-fingerprint", "chrome")
    if config.get("network") == "xhttp":
        opts = config.get("xhttp-opts", {})
        xhttp: dict[str, Any] = {
            "host": opts.get("host", config["servername"]),
            "path": opts.get("path", "/"),
        }
        if opts.get("mode"):
            xhttp["mode"] = opts["mode"]
        # the share link's `extra` is the same object, flattened into xhttpSettings
        xhttp.update(config.get("xhttp-extra", {}))
        stream = {
            "network": "xhttp",
            "security": "tls",
            "tlsSettings": {
                "serverName": config["servername"],
                "fingerprint": fingerprint,
                "alpn": config.get("alpn", ["h2"]),
            },
            "xhttpSettings": xhttp,
        }
    else:
        reality_opts = config.get("reality-opts", {})
        reality: dict[str, Any] = {
            "serverName": config["servername"],
            "fingerprint": reality_opts.get("fingerprint", fingerprint),
            "publicKey": reality_opts.get("public-key", ""),
            "shortId": reality_opts.get("short-id", ""),
        }
        if reality_opts.get("mldsa65-verify"):
            reality["mldsa65Verify"] = reality_opts["mldsa65-verify"]
        if reality_opts.get("spider-x"):
            reality["spiderX"] = reality_opts["spider-x"]
        stream = {"network": "raw", "security": "reality", "realitySettings": reality}
    outbound["streamSettings"] = stream
    return outbound


def _replace_placeholders(node: Any, outbounds: list[dict], route: dict[str, str]) -> Any:
    """Copy of `node` with the outbounds placeholder spliced in and PROXY rules routed."""
    if isinstance(node, list):
        out: list[Any] = []
        for item in node:
            if item == OUTBOUNDS_PLACEHOLDER:
                out.extend(copy.deepcopy(outbounds))
            else:
                out.append(_replace_placeholders(item, outbounds, route))
        return out
    if isinstance(node, dict):
        if ROUTE_PLACEHOLDER in (node.get("balancerTag"), node.get("outboundTag")):
            rule = {
                k: _replace_placeholders(v, outbounds, route)
                for k, v in node.items()
                if k not in ("balancerTag", "outboundTag")
            }
            rule.update(route)
            return rule
        return {k: _replace_placeholders(v, outbounds, route) for k, v in node.items()}
    return node


def build_config(
    skeleton: dict[str, Any], proxies: list[tuple[str, dict[str, Any]]], remarks: str
) -> dict[str, Any]:
    """One client config from the template skeleton: `proxies` (name, outbound) in priority order.

    The skeleton routes to the proxies with rules whose balancerTag/outboundTag is "PROXY"
    and lists "PROXY_OUTBOUNDS" among its outbounds. Several proxies get the failover chain
    (balancers, loopbacks, a burstObservatory over all but the last; the skeleton's own
    burstObservatory, if any, supplies the probe settings); a single one is routed to directly.
    """
    tags = [ob["tag"] for _, ob in proxies]
    outbounds = [ob for _, ob in proxies]
    balancers: list[dict[str, Any]] = []
    rules: list[dict[str, Any]] = []
    if len(proxies) > 1:
        for i, tag in enumerate(tags[:-1]):
            if i + 1 < len(tags) - 1:
                fallback = f"{LOOPBACK_PREFIX}{i + 1}"
                outbounds.append(
                    {
                        "tag": fallback,
                        "protocol": "loopback",
                        "settings": {"inboundTag": f"{BALANCER_PREFIX}{i + 1}-in"},
                    }
                )
                rules.append(
                    {
                        "inboundTag": [f"{BALANCER_PREFIX}{i + 1}-in"],
                        "balancerTag": f"{BALANCER_PREFIX}{i + 1}",
                    }
                )
            else:
                fallback = tags[-1]
            balancers.append(
                {
                    "tag": f"{BALANCER_PREFIX}{i}",
                    # selectors match tag prefixes: proxy-1 would also match proxy-10..19
                    "selector": [tag],
                    "strategy": {"type": "leastPing"},
                    "fallbackTag": fallback,
                }
            )
        route = {"balancerTag": f"{BALANCER_PREFIX}0"}
    else:
        route = {"outboundTag": tags[0]}

    config = _replace_placeholders(skeleton, outbounds, route)
    config["remarks"] = remarks
    routing = config.setdefault("routing", {})
    routing["rules"] = rules + routing.get("rules", [])
    if balancers:
        routing["balancers"] = balancers + routing.get("balancers", [])
        observatory = config.setdefault("burstObservatory", {})
        observatory["subjectSelector"] = tags[:-1]
        observatory.setdefault("pingConfig", {})
    else:
        config.pop("burstObservatory", None)
        config.pop("observatory", None)
    return config


def build_subscription(
    skeleton: dict[str, Any],
    proxy_configs: list[dict[str, Any]],
    auto_remarks: str,
) -> list[dict[str, Any]]:
    """Happ JSON subscription: the failover config first, then one config per server."""
    proxies: list[tuple[str, dict[str, Any]]] = []
    for config in proxy_configs:
        # proxy-1..9 stay distinct prefixes; more than nine servers would need padding
        outbound = to_xray_outbound(config, f"{TAG_PREFIX}{len(proxies) + 1}")
        if outbound is None:
            logger.warning(
                f"Happ JSON: {config.get('name')} ({config.get('type')}) has no Xray outbound, skipped"
            )
            continue
        proxies.append((config["name"], outbound))
    if not proxies:
        return []
    result = []
    if len(proxies) > 1:
        result.append(build_config(skeleton, proxies, auto_remarks))
    for name, outbound in proxies:
        single = dict(outbound, tag=f"{TAG_PREFIX}1")
        result.append(build_config(skeleton, [(name, single)], name))
    return result
