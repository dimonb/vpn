"""HAPP template processor: substitutes PROXY_LIST with proxy URLs."""

import base64
import json
import logging
import urllib.parse

from .processor import TemplateProcessor
from .proxy_config import ProxyConfig
from .xray_json import build_subscription

logger = logging.getLogger(__name__)


class HappProcessor:
    """Processor for HAPP templates."""

    def __init__(
        self,
        template_processor: TemplateProcessor,
        proxy_config: ProxyConfig | None = None,
    ):
        self.template_processor = template_processor
        self.proxy_config = proxy_config

    @staticmethod
    def _extract_query_params(
        request_headers: dict,
    ) -> tuple[str | None, str | None, str | None]:
        sub_name = password = user = None
        query_string = request_headers.get("x-query-string")
        if query_string:
            params = urllib.parse.parse_qs(query_string)
            if "sub" in params:
                sub_name = params["sub"][0]
            if "hash" in params:
                password = params["hash"][0]
            if "u" in params:
                user = params["u"][0]
        return sub_name, password, user

    def replace_proxy_list(self, tpl_text: str, request_headers: dict) -> str:
        """Replace lines that are exactly `PROXY_LIST` with generated proxy URLs."""
        if not self.proxy_config:
            logger.warning("No proxy config available, skipping PROXY_LIST replacement")
            return tpl_text

        sub_name, password, user = self._extract_query_params(request_headers)
        urls = self.proxy_config.get_proxy_urls(sub_name, password, user, flavor="happ")
        logger.info(f"HAPP: replacing PROXY_LIST with {len(urls)} URL(s)")

        replacement = "\n".join(urls)
        out_lines = []
        for line in tpl_text.split("\n"):
            if line.strip() == "PROXY_LIST":
                out_lines.append(replacement)
            else:
                out_lines.append(line)
        return "\n".join(out_lines)

    async def process_happ_config(
        self, tpl_text: str, incoming_host: str, request_headers: dict
    ) -> str:
        """Process HAPP template: drop #HAPP tag line, substitute PROXY_LIST, expand RULE-SETs."""
        stripped = self._strip_happ_tag(tpl_text)
        substituted = self.replace_proxy_list(stripped, request_headers)
        return await self.template_processor.process_template(
            substituted, incoming_host, request_headers
        )

    @staticmethod
    def _strip_happ_tag(tpl_text: str) -> str:
        """Remove the leading `#HAPP` tag line (and a single following blank line)."""
        lines = tpl_text.split("\n")
        # Find first non-empty line — that's where the tag lives
        for i, line in enumerate(lines):
            if line.strip() == "":
                continue
            if line.strip().startswith("#"):
                tags = [t.strip().upper() for t in line.strip()[1:].split(",")]
                if "HAPP" in tags:
                    del lines[i]
                    if i < len(lines) and lines[i].strip() == "":
                        del lines[i]
            break
        return "\n".join(lines)


def split_happ_json_template(tpl_text: str) -> tuple[dict[str, str], str]:
    """Split a `#HAPP,JSON` template into Happ directives and the JSON skeleton.

    Leading `#key: value` lines become response headers (a JSON body has no room for
    them); the tag line and other bare `#` lines are dropped. The rest is the skeleton.
    """
    headers: dict[str, str] = {}
    lines = tpl_text.split("\n")
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        if line and not line.startswith("#"):
            break
        if line.startswith("#") and ":" in line:
            key, value = line[1:].split(":", 1)
            key = key.strip()
            if key and " " not in key:
                value = value.strip()
                if not value.isascii():
                    # header values are latin-1; Happ takes UTF-8 text as `base64:<…>`
                    value = "base64:" + base64.b64encode(value.encode()).decode()
                headers[key] = value
        i += 1
    return headers, "\n".join(lines[i:])


def process_happ_json(
    tpl_text: str, proxy_config: ProxyConfig | None, request_headers: dict
) -> tuple[str, dict[str, str]]:
    """Body and headers for a Happ JSON subscription (see xray_json)."""
    headers, skeleton_text = split_happ_json_template(tpl_text)
    skeleton = json.loads(skeleton_text)
    auto_remarks = skeleton.pop("remarks", "Auto")
    configs: list = []
    if proxy_config:
        sub_name, password, user = HappProcessor._extract_query_params(request_headers)
        proxy_configs = proxy_config.generate_proxy_configs(sub_name, password, user)
        configs = build_subscription(skeleton, proxy_configs, auto_remarks)
    else:
        logger.warning("No proxy config available, Happ JSON subscription is empty")
    logger.info(f"HAPP JSON: {len(configs)} config(s)")
    return json.dumps(configs, ensure_ascii=False, indent=1), headers
