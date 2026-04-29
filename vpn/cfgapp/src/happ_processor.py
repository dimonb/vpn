"""HAPP template processor: substitutes PROXY_LIST with proxy URLs."""

import logging
import urllib.parse

from .processor import TemplateProcessor
from .proxy_config import ProxyConfig

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

    def _extract_query_params(self, request_headers: dict) -> tuple[str | None, str | None, str | None]:
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
