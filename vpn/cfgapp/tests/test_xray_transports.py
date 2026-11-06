"""XHTTP entries and the mihomo subscription headers."""

import base64
import hashlib
import json
import urllib.parse
from pathlib import Path

import pytest

from src.config import settings
from src.main import clash_subscription_headers
from src.proxy_config import ProxyConfig

SALT = "test-salt"


def vless_id(seed: str) -> str:
    h = hashlib.sha256(seed.encode()).hexdigest()
    return f"{h[:8]}-{h[8:12]}-{h[12:16]}-{h[16:20]}-{h[20:32]}"


@pytest.fixture
def xray_settings(monkeypatch):
    monkeypatch.setattr(settings, "salt", SALT)
    monkeypatch.setattr(settings, "obfs_password", "obfs-secret")
    monkeypatch.setattr(settings, "xhttp_path", "secretpath")
    monkeypatch.setattr(settings, "xhttp_mode", "")
    monkeypatch.setattr(settings, "https_port", 443)
    monkeypatch.setattr(settings, "profile_update_interval", "")
    monkeypatch.setattr(settings, "profile_title", "")


@pytest.fixture
def proxy_config(tmp_path: Path) -> ProxyConfig:
    config = {
        "users": ["alice"],
        "subs": {
            "regions": {
                "🇮🇪 Ireland": {
                    "protocol": "xhttp",
                    "host": "entry.example.net",
                    "exit": "exit-ie.example.net",
                },
                "🇦🇲 Armenia": {
                    "protocol": "xhttp",
                    "host": "entry.example.net",
                    "exit": "exit-am.example.net",
                },
            },
            "direct": {
                "Direct": {"protocol": "xhttp", "host": "exit-ie.example.net"},
            },
        },
    }
    path = tmp_path / "config.json"
    path.write_text(json.dumps(config, ensure_ascii=False))
    return ProxyConfig(str(path))


def test_relay_entries_carry_one_id_per_exit(xray_settings, proxy_config):
    proxies = proxy_config.generate_proxy_configs("regions", None, "alice")
    assert [p["name"] for p in proxies] == ["🇮🇪 Ireland", "🇦🇲 Armenia"]
    ie, am = proxies
    # Same derivation as vpn/xray.json.j2 on the relay: sha256("<user>.<exit>.<SALT>")
    assert ie["uuid"] == vless_id(f"alice.exit-ie.example.net.{SALT}")
    assert am["uuid"] == vless_id(f"alice.exit-am.example.net.{SALT}")
    assert ie["uuid"] != am["uuid"]
    assert ie["server"] == "entry.example.net"
    assert ie["servername"] == "entry.example.net"
    assert ie["port"] == 443
    assert ie["tls"] is True
    assert ie["network"] == "xhttp"
    assert ie["xhttp-opts"] == {"path": "/secretpath", "host": "entry.example.net"}


def test_direct_xhttp_uses_the_per_user_id(xray_settings, proxy_config):
    direct = proxy_config.generate_proxy_configs("direct", None, "alice")[0]
    assert direct["uuid"] == vless_id(f"alice.{SALT}")


def test_xhttp_mode_is_passed_through(xray_settings, proxy_config, monkeypatch):
    monkeypatch.setattr(settings, "xhttp_mode", "stream-up")
    ie = proxy_config.generate_proxy_configs("regions", None, "alice")[0]
    assert ie["xhttp-opts"]["mode"] == "stream-up"


def test_xhttp_needs_a_user_and_a_path(xray_settings, proxy_config, monkeypatch):
    assert proxy_config.generate_proxy_configs("regions", None, None) == []
    monkeypatch.setattr(settings, "xhttp_path", "")
    assert proxy_config.generate_proxy_configs("regions", None, "alice") == []


def test_share_links_skip_xhttp(xray_settings, proxy_config):
    # XHTTP entries are for mihomo subscriptions; the link formats do not describe them.
    assert proxy_config.get_proxy_urls("regions", None, "alice") == []


def test_subscription_headers_off_by_default(xray_settings):
    assert clash_subscription_headers() == {}


def test_subscription_headers(xray_settings, monkeypatch):
    monkeypatch.setattr(settings, "profile_update_interval", "1")
    monkeypatch.setattr(settings, "profile_title", "Corp VPN")
    headers = clash_subscription_headers()
    assert headers["profile-update-interval"] == "1"
    assert headers["profile-title"] == "Corp VPN"
    assert headers["content-disposition"] == "attachment; filename*=UTF-8''Corp%20VPN.yaml"


def test_subscription_title_non_ascii_is_base64(xray_settings, monkeypatch):
    monkeypatch.setattr(settings, "profile_title", "ВПН")
    headers = clash_subscription_headers()
    assert headers["profile-title"] == "base64:" + base64.b64encode("ВПН".encode()).decode()
    assert headers["content-disposition"].endswith(urllib.parse.quote("ВПН.yaml"))


def test_proxy_list_names_the_per_user_entries(xray_settings, proxy_config):
    # PROXY_LIST (the select group) must name exactly the entries PROXY_CONFIGS produced.
    assert proxy_config.get_proxy_list("regions", None, "alice") == ["🇮🇪 Ireland", "🇦🇲 Armenia"]
