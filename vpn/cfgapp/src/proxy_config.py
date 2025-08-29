"""Proxy configuration management and generation."""

import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

from .config import settings

logger = logging.getLogger(__name__)


class ProxyConfig:
    """Proxy configuration manager."""

    def __init__(self, config_path: str):
        """Initialize proxy configuration.

        Args:
            config_path: Path to the proxy configuration file
        """
        self.config_path = Path(config_path)
        self.config_data = self._load_config()

    def _load_config(self) -> Dict[str, Any]:
        """Load configuration from file.

        Returns:
            Configuration data as dictionary

        Raises:
            FileNotFoundError: If config file doesn't exist
            json.JSONDecodeError: If config file is invalid JSON
        """
        if not self.config_path.exists():
            raise FileNotFoundError(f"Proxy config file not found: {self.config_path}")

        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
            logger.info(f"Loaded proxy config from {self.config_path}")
            return config
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in proxy config file: {e}")
            raise

    def get_users(self) -> List[str]:
        """Get list of users from configuration.

        Returns:
            List of user names
        """
        return self.config_data.get('users', [])

    def get_subs(self) -> Dict[str, Any]:
        """Get subscriptions configuration.

        Returns:
            Subscriptions configuration
        """
        return self.config_data.get('subs', {})

    def get_subscription_proxies(self, sub_name: Optional[str] = None) -> Dict[str, Any]:
        """Get proxies for specific subscription.

        Args:
            sub_name: Subscription name, defaults to 'default'

        Returns:
            Dictionary of proxy configurations for the subscription
        """
        subs = self.get_subs()
        if not sub_name:
            sub_name = 'default'
        
        if sub_name not in subs:
            logger.warning(f"Subscription '{sub_name}' not found, using 'default'")
            sub_name = 'default'
        
        return subs.get(sub_name, {})

    def generate_proxy_configs(self, sub_name: Optional[str] = None, password: Optional[str] = None) -> List[Dict[str, Any]]:
        """Generate proxy configurations for all protocols in subscription.

        Args:
            sub_name: Subscription name, defaults to 'default'
            password: Password from query parameter (optional)

        Returns:
            List of proxy configurations (one per proxy in subscription)
        """
        proxy_configs = []
        subscription_proxies = self.get_subscription_proxies(sub_name)

        for proxy_name, proxy_config in subscription_proxies.items():
            protocol = proxy_config.get('protocol', '')
            host = proxy_config.get('host', '')

            if not protocol or not host:
                logger.warning(f"Invalid proxy config: {proxy_name}")
                continue

            # Generate one config per proxy (not per user)
            proxy_config = self._generate_proxy_config(
                protocol, host, proxy_name, password
            )
            if proxy_config:
                proxy_configs.append(proxy_config)

        logger.info(f"Generated {len(proxy_configs)} proxy configurations for subscription '{sub_name or 'default'}'")
        return proxy_configs

    def _generate_proxy_config(self, protocol: str, host: str, 
                              proxy_name: str, password: Optional[str] = None) -> Dict[str, Any]:
        """Generate proxy configuration for specific protocol.

        Args:
            protocol: Proxy protocol (e.g., 'hy2', 'vmess', etc.)
            host: Proxy host
            proxy_name: Proxy name
            password: Password from query parameter (optional)

        Returns:
            Proxy configuration dictionary
        """
        if protocol == 'hy2':
            return self._generate_hysteria2_config(host, proxy_name, password)
        elif protocol == 'vmess':
            return self._generate_vmess_config(host, proxy_name)
        elif protocol == 'vless':
            return self._generate_vless_config(host, proxy_name)
        else:
            logger.warning(f"Unsupported protocol: {protocol}")
            return {}

    def _generate_hysteria2_config(self, host: str, proxy_name: str, password: Optional[str] = None) -> Dict[str, Any]:
        """Generate Hysteria2 proxy configuration.

        Args:
            host: Proxy host
            proxy_name: Proxy name
            password: Password from query parameter (optional)

        Returns:
            Hysteria2 configuration dictionary
        """
        # Generate unique name
        name = f"{proxy_name.lower()}"
        
        # Use provided password or generate one
        if password:
            proxy_password = password
        else:
            proxy_password = self._generate_password(proxy_name)
            
        port = settings.hysteria2_port  # Use fixed port from environment variable
        
        return {
            "name": name,
            "type": "hysteria2",
            "server": host,
            "port": port,
            "password": proxy_password,
            "sni": "i.am.com",
            "skip-cert-verify": True,
            "alpn": ["h3"],
            "up": 50,
            "down": 200,
            "obfs": "salamander",
            "obfs-password": settings.obfs_password,
            "fast-open": True,
            "udp": True
        }

    def _generate_vmess_config(self, host: str, proxy_name: str) -> Dict[str, Any]:
        """Generate VMess proxy configuration.

        Args:
            host: Proxy host
            proxy_name: Proxy name

        Returns:
            VMess configuration dictionary
        """
        name = f"{proxy_name.lower()}"
        uuid = self._generate_uuid(proxy_name)
        port = self._generate_port(proxy_name)
        
        return {
            "name": name,
            "type": "vmess",
            "server": host,
            "port": port,
            "uuid": uuid,
            "alterId": 0,
            "cipher": "auto",
            "tls": True,
            "servername": host,
            "skip-cert-verify": True,
            "udp": True
        }

    def _generate_vless_config(self, host: str, proxy_name: str) -> Dict[str, Any]:
        """Generate VLESS proxy configuration.

        Args:
            host: Proxy host
            proxy_name: Proxy name

        Returns:
            VLESS configuration dictionary
        """
        name = f"{proxy_name.lower()}"
        uuid = self._generate_uuid(proxy_name)
        port = self._generate_port(proxy_name)
        
        return {
            "name": name,
            "type": "vless",
            "server": host,
            "port": port,
            "uuid": uuid,
            "network": "ws",
            "tls": True,
            "servername": host,
            "skip-cert-verify": True,
            "udp": True
        }

    def _generate_password(self, proxy_name: str) -> str:
        """Generate password for proxy.

        Args:
            proxy_name: Proxy name

        Returns:
            Generated password
        """
        # Simple hash-based generation for demo
        import hashlib
        base = f"{proxy_name}"
        return hashlib.sha256(base.encode()).hexdigest()

    def _generate_port(self, proxy_name: str) -> int:
        """Generate port for proxy.

        Args:
            proxy_name: Proxy name

        Returns:
            Generated port number
        """
        # Simple hash-based generation for demo
        import hashlib
        base = f"{proxy_name}:port"
        hash_val = int(hashlib.md5(base.encode()).hexdigest()[:8], 16)
        return 40000 + (hash_val % 10000)

    def _generate_uuid(self, proxy_name: str) -> str:
        """Generate UUID for proxy.

        Args:
            proxy_name: Proxy name

        Returns:
            Generated UUID
        """
        import hashlib
        import uuid
        
        base = f"{proxy_name}:uuid"
        hash_val = hashlib.md5(base.encode()).hexdigest()
        
        # Convert to UUID format
        return str(uuid.UUID(hash_val))

    def get_proxy_list(self, sub_name: Optional[str] = None, password: Optional[str] = None) -> List[str]:
        """Get list of proxy names for PROXY_LIST.

        Args:
            sub_name: Subscription name, defaults to 'default'
            password: Password from query parameter (optional)

        Returns:
            List of proxy names
        """
        proxy_configs = self.generate_proxy_configs(sub_name, password)
        return [config['name'] for config in proxy_configs]
