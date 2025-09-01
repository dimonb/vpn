"""CLASH YAML configuration processor."""

import logging
from typing import Any

import yaml

from .processor import TemplateProcessor
from .proxy_config import ProxyConfig

logger = logging.getLogger(__name__)


class ClashProcessor:
    """Processor for CLASH YAML configurations."""

    def __init__(
        self,
        template_processor: TemplateProcessor,
        proxy_config: ProxyConfig | None = None,
    ):
        """Initialize CLASH processor.

        Args:
            template_processor: TemplateProcessor instance for RULE-SET expansion
            proxy_config: Optional ProxyConfig instance for proxy generation
        """
        self.template_processor = template_processor
        self.proxy_config = proxy_config

    def parse_clash_yaml(self, yaml_content: str) -> dict[str, Any]:
        """Parse CLASH YAML content.

        Args:
            yaml_content: Raw YAML content as string

        Returns:
            Parsed YAML as dictionary
        """
        return yaml.safe_load(yaml_content)

    def extract_rule_sets(self, clash_config: dict[str, Any]) -> list[dict[str, Any]]:
        """Extract RULE-SET entries from CLASH configuration.

        Args:
            clash_config: Parsed CLASH configuration

        Returns:
            List of RULE-SET entries with their context
        """
        rule_sets = []

        # Look for RULE-SET entries in rules section
        rules = clash_config.get("rules", [])
        for i, rule in enumerate(rules):
            if isinstance(rule, str) and rule.startswith("RULE-SET,"):
                # Parse RULE-SET entry
                parts = rule.split(",", 2)
                if len(parts) >= 3:
                    url = parts[1].strip()
                    proxy_group = parts[2].strip()
                    rule_sets.append(
                        {
                            "index": i,
                            "url": url,
                            "proxy_group": proxy_group,
                            "original_rule": rule,
                        }
                    )

        return rule_sets

    async def expand_rule_sets(
        self, rule_sets: list[dict[str, Any]], incoming_host: str, request_headers: dict
    ) -> list[list[str]]:
        """Expand RULE-SET entries using the template processor.

        Args:
            rule_sets: List of RULE-SET entries
            incoming_host: Incoming request host
            request_headers: Request headers

        Returns:
            List of expanded rules for each RULE-SET (list of lists)
        """
        expanded_rules_list = []

        for rule_set in rule_sets:
            url = rule_set["url"]
            proxy_group = rule_set["proxy_group"]

            # Create a temporary template with just this RULE-SET
            temp_template = f"RULE-SET,{url},{proxy_group}"

            # Use template processor to expand it
            expanded = await self.template_processor.process_template(
                temp_template, incoming_host, request_headers
            )

            # Add expanded rules (skip the first line which is the comment)
            lines = expanded.split("\n")
            if lines and lines[0].startswith("# RULE-SET"):
                expanded_rules_list.append(lines[1:])
            else:
                expanded_rules_list.append(lines)

        return expanded_rules_list

    def replace_proxy_placeholders(
        self, clash_config: dict[str, Any], request_headers: dict
    ) -> dict[str, Any]:
        """Replace PROXY_CONFIGS and PROXY_LIST placeholders with actual data.

        Args:
            clash_config: Parsed CLASH configuration
            request_headers: Request headers to extract query parameters

        Returns:
            Updated CLASH configuration with replaced placeholders
        """
        if not self.proxy_config:
            logger.warning(
                "No proxy config available, skipping proxy placeholder replacement"
            )
            return clash_config

        try:
            # Extract sub parameter, hash, and user from headers (if available)
            sub_name = None
            password = None
            user = None
            if "x-query-string" in request_headers:
                # Parse query string to find 'sub', 'hash', and 'u' parameters
                import urllib.parse

                query_string = request_headers["x-query-string"]
                query_params = urllib.parse.parse_qs(query_string)
                if "sub" in query_params:
                    sub_name = query_params["sub"][0]
                    logger.info(f"Using subscription: {sub_name}")
                if "hash" in query_params:
                    password = query_params["hash"][0]
                    logger.info("Using password from hash parameter")
                if "u" in query_params:
                    user = query_params["u"][0]
                    logger.info(f"Using user: {user}")

            # Replace PROXY_CONFIGS in proxies section
            if "proxies" in clash_config:
                proxies = clash_config["proxies"]
                if (
                    isinstance(proxies, list)
                    and len(proxies) == 1
                    and proxies[0] == "PROXY_CONFIGS"
                ):
                    proxy_configs = self.proxy_config.generate_proxy_configs(
                        sub_name, password, user
                    )
                    clash_config["proxies"] = proxy_configs
                    logger.info(
                        f"Replaced PROXY_CONFIGS with {len(proxy_configs)} proxy configurations"
                    )

            # Replace PROXY_LIST in proxy-groups section
            if "proxy-groups" in clash_config:
                for group in clash_config["proxy-groups"]:
                    if isinstance(group, dict) and "proxies" in group:
                        proxies = group["proxies"]
                        if (
                            isinstance(proxies, list)
                            and len(proxies) == 1
                            and proxies[0] == "PROXY_LIST"
                        ):
                            proxy_list = self.proxy_config.get_proxy_list(
                                sub_name, password
                            )
                            group["proxies"] = proxy_list
                            logger.info(
                                f"Replaced PROXY_LIST with {len(proxy_list)} proxy names"
                            )

        except Exception as e:
            logger.error(f"Error replacing proxy placeholders: {e}")

        return clash_config

    async def process_clash_config(
        self, yaml_content: str, incoming_host: str, request_headers: dict
    ) -> str:
        """Process CLASH YAML configuration and expand RULE-SET entries.

        Args:
            yaml_content: Raw YAML content
            incoming_host: Incoming request host
            request_headers: Request headers

        Returns:
            Processed YAML content with expanded RULE-SET entries
        """
        # Parse YAML
        clash_config = self.parse_clash_yaml(yaml_content)

        # Replace proxy placeholders first
        clash_config = self.replace_proxy_placeholders(clash_config, request_headers)

        # Extract RULE-SET entries
        rule_sets = self.extract_rule_sets(clash_config)

        if not rule_sets:
            # No RULE-SET entries found, return processed content
            return yaml.dump(clash_config, default_flow_style=False, allow_unicode=True)

        # Expand RULE-SET entries
        expanded_rules_list = await self.expand_rule_sets(
            rule_sets, incoming_host, request_headers
        )

        # Replace RULE-SET entries with expanded rules in order
        rules = clash_config.get("rules", [])
        new_rules = []
        rule_set_index = 0

        for rule in rules:
            if isinstance(rule, str) and rule.startswith("RULE-SET,"):
                # Replace RULE-SET entry with its expanded rules
                if rule_set_index < len(expanded_rules_list):
                    new_rules.extend(expanded_rules_list[rule_set_index])
                    rule_set_index += 1
            else:
                new_rules.append(rule)

        # Update configuration
        clash_config["rules"] = new_rules

        # Convert back to YAML
        return yaml.dump(
            clash_config, default_flow_style=False, allow_unicode=True, sort_keys=False
        )
