"""Happ JSON subscriptions: Xray outbounds and the ordered failover chain (src/xray_json.py)."""

import base64
import json

from src.happ_processor import split_happ_json_template
from src.xray_json import build_subscription, to_xray_outbound

SKELETON = {
    "remarks": "Auto",
    "inbounds": [{"tag": "socks", "port": 10808, "protocol": "socks"}],
    "outbounds": [
        "PROXY_OUTBOUNDS",
        {"tag": "direct", "protocol": "freedom"},
        {"tag": "block", "protocol": "blackhole"},
    ],
    "routing": {
        "rules": [
            {"ip": ["10.0.0.0/8"], "outboundTag": "direct"},
            {"network": "tcp,udp", "balancerTag": "PROXY"},
        ]
    },
    "burstObservatory": {"pingConfig": {"interval": "15s", "sampling": 2}},
}

REALITY = {
    "name": "relay",
    "type": "vless",
    "server": "relay.example.net",
    "port": 443,
    "uuid": "11111111-2222-3333-4444-555555555555",
    "flow": "xtls-rprx-vision",
    "servername": "sni.example.com",
    "client-fingerprint": "chrome",
    "reality-opts": {"public-key": "PBK", "short-id": "abcd"},
}

XHTTP_CDN = {
    "name": "cdn",
    "type": "vless",
    "server": "cdn.example.net",
    "port": 443,
    "uuid": "66666666-7777-8888-9999-000000000000",
    "servername": "cdn.example.net",
    "alpn": ["h2"],
    "client-fingerprint": "chrome",
    "network": "xhttp",
    "xhttp-opts": {"path": "/secret", "host": "cdn.example.net", "mode": "packet-up"},
    "encryption": "mlkem768x25519plus.random.0rtt.KEY",
    "xhttp-extra": {"uplinkHTTPMethod": "GET", "uplinkDataPlacement": "header"},
}


def test_reality_outbound():
    ob = to_xray_outbound(REALITY, "proxy-1")
    user = ob["settings"]["vnext"][0]["users"][0]
    assert user == {
        "id": REALITY["uuid"],
        "encryption": "none",
        "flow": "xtls-rprx-vision",
    }
    ss = ob["streamSettings"]
    assert ss["network"] == "raw" and ss["security"] == "reality"
    assert ss["realitySettings"] == {
        "serverName": "sni.example.com",
        "fingerprint": "chrome",
        "publicKey": "PBK",
        "shortId": "abcd",
    }


def test_reality_v2_carries_mldsa65_verify():
    cfg = dict(
        REALITY,
        **{
            "reality-opts": {
                "public-key": "P",
                "short-id": "3e3e",
                "mldsa65-verify": "V",
            }
        },
    )
    assert (
        to_xray_outbound(cfg, "t")["streamSettings"]["realitySettings"]["mldsa65Verify"]
        == "V"
    )


def test_xhttp_cdn_outbound():
    ob = to_xray_outbound(XHTTP_CDN, "proxy-3")
    user = ob["settings"]["vnext"][0]["users"][0]
    assert user["encryption"] == XHTTP_CDN["encryption"] and "flow" not in user
    ss = ob["streamSettings"]
    assert ss["network"] == "xhttp" and ss["security"] == "tls"
    assert ss["tlsSettings"]["serverName"] == "cdn.example.net"
    assert ss["xhttpSettings"] == {
        "host": "cdn.example.net",
        "path": "/secret",
        "mode": "packet-up",
        "uplinkHTTPMethod": "GET",
        "uplinkDataPlacement": "header",
    }


def test_non_vless_has_no_outbound():
    assert to_xray_outbound({"type": "hysteria2", "name": "h"}, "t") is None


def _rules(cfg):
    return cfg["routing"]["rules"]


def test_failover_chain_in_group_order():
    a = dict(REALITY, name="first")
    b = dict(REALITY, name="second", server="second.example.net")
    subs = build_subscription(SKELETON, [a, b, XHTTP_CDN], "Auto")
    assert [c["remarks"] for c in subs] == ["Auto", "first", "second", "cdn"]

    auto = subs[0]
    tags = [o["tag"] for o in auto["outbounds"]]
    assert tags == ["proxy-1", "proxy-2", "proxy-3", "to-failover-1", "direct", "block"]
    assert auto["outbounds"][3] == {
        "tag": "to-failover-1",
        "protocol": "loopback",
        "settings": {"inboundTag": "failover-1-in"},
    }
    assert auto["routing"]["balancers"] == [
        {
            "tag": "failover-0",
            "selector": ["proxy-1"],
            "strategy": {"type": "leastPing"},
            "fallbackTag": "to-failover-1",
        },
        {
            "tag": "failover-1",
            "selector": ["proxy-2"],
            "strategy": {"type": "leastPing"},
            "fallbackTag": "proxy-3",
        },
    ]
    # loopback traffic re-enters routing first; the template's own rules keep their order
    assert _rules(auto) == [
        {"inboundTag": ["failover-1-in"], "balancerTag": "failover-1"},
        {"ip": ["10.0.0.0/8"], "outboundTag": "direct"},
        {"network": "tcp,udp", "balancerTag": "failover-0"},
    ]
    # the last server is the unconditional fallback, so only the others are probed
    assert auto["burstObservatory"] == {
        "pingConfig": {"interval": "15s", "sampling": 2},
        "subjectSelector": ["proxy-1", "proxy-2"],
    }


def test_two_servers_need_no_loopback():
    auto = build_subscription(SKELETON, [REALITY, XHTTP_CDN], "Auto")[0]
    assert [o["protocol"] for o in auto["outbounds"]][:3] == [
        "vless",
        "vless",
        "freedom",
    ]
    assert auto["routing"]["balancers"] == [
        {
            "tag": "failover-0",
            "selector": ["proxy-1"],
            "strategy": {"type": "leastPing"},
            "fallbackTag": "proxy-2",
        }
    ]


def test_single_server_configs_route_directly():
    subs = build_subscription(SKELETON, [REALITY, XHTTP_CDN], "Auto")
    for cfg in subs[1:]:
        assert [o["tag"] for o in cfg["outbounds"]] == ["proxy-1", "direct", "block"]
        assert _rules(cfg)[-1] == {"network": "tcp,udp", "outboundTag": "proxy-1"}
        assert "balancers" not in cfg["routing"] and "burstObservatory" not in cfg
    assert subs[2]["outbounds"][0]["streamSettings"]["network"] == "xhttp"


def test_one_server_gets_no_auto_entry():
    subs = build_subscription(SKELETON, [REALITY], "Auto")
    assert [c["remarks"] for c in subs] == ["relay"]


def test_skeleton_is_not_mutated():
    before = json.dumps(SKELETON, sort_keys=True)
    build_subscription(SKELETON, [REALITY, dict(REALITY, name="b"), XHTTP_CDN], "Auto")
    assert json.dumps(SKELETON, sort_keys=True) == before


def test_unsupported_entries_are_skipped():
    subs = build_subscription(
        SKELETON, [{"type": "hysteria2", "name": "h"}, REALITY], "Auto"
    )
    assert [c["remarks"] for c in subs] == ["relay"]


def test_template_directives_become_headers():
    tpl = '#HAPP,JSON,AUTH\n#profile-title: my.profile\n#profile-update-interval: 6\n#announce: Привет\n{"a": 1}\n'
    headers, body = split_happ_json_template(tpl)
    assert headers["profile-title"] == "my.profile"
    assert headers["profile-update-interval"] == "6"
    assert (
        headers["announce"] == "base64:" + base64.b64encode("Привет".encode()).decode()
    )
    assert "HAPP,JSON,AUTH" not in headers
    assert json.loads(body) == {"a": 1}


def test_endpoint_serves_json_with_directive_headers():
    """`#HAPP,JSON` template: JSON body, `#key: value` lines as headers, no RULE-SET expansion."""
    from unittest.mock import Mock, patch

    import httpx
    from fastapi.testclient import TestClient

    import src.main as main

    tpl = "#HAPP,JSON\n#profile-title: auto.profile\n" + json.dumps(SKELETON)
    req = httpx.Request("GET", "https://example.com/auto.conf")
    responses = [
        httpx.Response(404, content=b"", request=req),
        httpx.Response(200, content=tpl.encode(), request=req),
    ]
    proxy_config = Mock()
    proxy_config.generate_proxy_configs.return_value = [REALITY, XHTTP_CDN]
    with (
        patch("src.main.forward_request", side_effect=responses),
        patch.object(main, "proxy_config", proxy_config),
    ):
        response = TestClient(main.app).get("/auto.conf?sub=auto&u=someone")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/json")
    assert response.headers["profile-title"] == "auto.profile"
    body = response.json()
    assert [c["remarks"] for c in body] == ["Auto", "relay", "cdn"]
    proxy_config.generate_proxy_configs.assert_called_once_with("auto", None, "someone")
