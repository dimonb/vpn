"""Tests for HappProcessor."""

import json
import tempfile
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock

import pytest

from src.happ_processor import HappProcessor
from src.processor import TemplateProcessor
from src.proxy_config import ProxyConfig


@pytest.fixture
def sample_config() -> dict[str, Any]:
    return {
        "users": ["dimonb"],
        "subs": {
            "default": {
                "DE_1_CONTABO": {
                    "protocol": "hy2",
                    "host": "de-1.contabo.v.dimonb.com",
                },
                "RU_1_KVMKI": {
                    "protocol": "vless",
                    "host": "ru-1.kvmki.v.dimonb.com",
                },
                "RU_2_KVMKI": {
                    "protocol": "vless-v2",
                    "host": "ru-2.kvmki.v.dimonb.com",
                },
            }
        },
    }


@pytest.fixture
def config_file(sample_config: dict[str, Any]) -> Path:
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json.dump(sample_config, f)
        return Path(f.name)


@pytest.fixture
def proxy_config(config_file: Path) -> ProxyConfig:
    return ProxyConfig(str(config_file))


@pytest.fixture
def template_processor() -> TemplateProcessor:
    return TemplateProcessor(http_client=AsyncMock())


HAPP_TPL = """#HAPP

#profile-title: dimonb-happ-ru
#proxy-enable: 1
#tun-enable: 1
happ://routing/onadd/

PROXY_LIST
"""


def test_replace_proxy_list_substitutes_urls(
    template_processor: TemplateProcessor, proxy_config: ProxyConfig
) -> None:
    happ = HappProcessor(template_processor, proxy_config)
    out = happ.replace_proxy_list(HAPP_TPL, request_headers={"x-query-string": "u=dimonb"})

    # PROXY_LIST line is gone
    assert "PROXY_LIST" not in out
    # Should contain proxy URLs (3 proxies in default sub)
    lines = [line for line in out.split("\n") if line.strip()]
    proxy_url_lines = [
        line for line in lines if line.startswith(("vless://", "hysteria2://", "vmess://"))
    ]
    assert len(proxy_url_lines) == 3
    # Static template lines preserved
    assert "#profile-title: dimonb-happ-ru" in out
    assert "happ://routing/onadd/" in out


def test_replace_proxy_list_no_proxy_config(template_processor: TemplateProcessor) -> None:
    happ = HappProcessor(template_processor, proxy_config=None)
    out = happ.replace_proxy_list(HAPP_TPL, request_headers={})
    assert "PROXY_LIST" in out


@pytest.mark.asyncio
async def test_process_happ_config_runs_through_template_processor(
    proxy_config: ProxyConfig,
) -> None:
    fake_processor = AsyncMock(spec=TemplateProcessor)
    fake_processor.process_template.return_value = "OK"
    happ = HappProcessor(fake_processor, proxy_config)

    result = await happ.process_happ_config(
        HAPP_TPL, incoming_host="h", request_headers={"x-query-string": "u=dimonb"}
    )

    assert result == "OK"
    # process_template received text with PROXY_LIST already substituted
    passed_text = fake_processor.process_template.call_args[0][0]
    assert "PROXY_LIST" not in passed_text
    assert "#HAPP" not in passed_text
    assert "vless://" in passed_text or "hysteria2://" in passed_text
