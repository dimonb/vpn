"""Proxy configuration management and generation."""

import json
import logging
from pathlib import Path
from typing import Any, Dict, List

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

    def generate_proxy_configs(self) -> List[Dict[str, Any]]:
        """Generate proxy configurations for all protocols and users.

        Returns:
            List of proxy configurations
        """
        proxy_configs = []
        users = self.get_users()
        subs = self.get_subs()

        for sub_name, sub_config in subs.items():
            for proxy_name, proxy_config in sub_config.items():
                protocol = proxy_config.get('protocol', '')
                host = proxy_config.get('host', '')

                if not protocol or not host:
                    logger.warning(f"Invalid proxy config: {proxy_name}")
                    continue

                # Generate config for each user
                for user in users:
                    proxy_config = self._generate_proxy_config(
                        protocol, host, user, proxy_name
                    )
                    if proxy_config:
                        proxy_configs.append(proxy_config)

        logger.info(f"Generated {len(proxy_configs)} proxy configurations")
        return proxy_configs

    def _generate_proxy_config(self, protocol: str, host: str, 
                              user: str, proxy_name: str) -> Dict[str, Any]:
        """Generate proxy configuration for specific protocol.

        Args:
            protocol: Proxy protocol (e.g., 'hy2', 'vmess', etc.)
            host: Proxy host
            user: Username
            proxy_name: Proxy name

        Returns:
            Proxy configuration dictionary
        """
        if protocol == 'hy2':
            return self._generate_hysteria2_config(host, user, proxy_name)
        elif protocol == 'vmess':
            return self._generate_vmess_config(host, user, proxy_name)
        elif protocol == 'vless':
            return self._generate_vless_config(host, user, proxy_name)
        else:
            logger.warning(f"Unsupported protocol: {protocol}")
            return {}

    def _generate_hysteria2_config(self, host: str, user: str, 
                                  proxy_name: str) -> Dict[str, Any]:
        """Generate Hysteria2 proxy configuration.

        Args:
            host: Proxy host
            user: Username
            proxy_name: Proxy name

        Returns:
            Hysteria2 configuration dictionary
        """
        # Generate unique name
        name = f"{proxy_name.lower()}-{user}"
        
        # Generate random password and other parameters
        # In real implementation, these would be generated based on user/proxy
        password = self._generate_password(user, proxy_name)
        port = self._generate_port(user, proxy_name)
        
        return {
            "name": name,
            "type": "hysteria2",
            "server": host,
            "port": port,
            "password": password,
            "sni": host,
            "skip-cert-verify": True,
            "alpn": ["h3"],
            "up": 50,
            "down": 50,
            "obfs": "salamander",
            "obfs-password": self._generate_obfs_password(user, proxy_name),
            "fast-open": True,
            "udp": True
        }

    def _generate_vmess_config(self, host: str, user: str, 
                              proxy_name: str) -> Dict[str, Any]:
        """Generate VMess proxy configuration.

        Args:
            host: Proxy host
            user: Username
            proxy_name: Proxy name

        Returns:
            VMess configuration dictionary
        """
        name = f"{proxy_name.lower()}-{user}"
        uuid = self._generate_uuid(user, proxy_name)
        port = self._generate_port(user, proxy_name)
        
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

    def _generate_vless_config(self, host: str, user: str, 
                              proxy_name: str) -> Dict[str, Any]:
        """Generate VLESS proxy configuration.

        Args:
            host: Proxy host
            user: Username
            proxy_name: Proxy name

        Returns:
            VLESS configuration dictionary
        """
        name = f"{proxy_name.lower()}-{user}"
        uuid = self._generate_uuid(user, proxy_name)
        port = self._generate_port(user, proxy_name)
        
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

    def _generate_password(self, user: str, proxy_name: str) -> str:
        """Generate password for proxy.

        Args:
            user: Username
            proxy_name: Proxy name

        Returns:
            Generated password
        """
        # Simple hash-based generation for demo
        import hashlib
        base = f"{user}:{proxy_name}"
        return hashlib.md5(base.encode()).hexdigest()[:20]

    def _generate_port(self, user: str, proxy_name: str) -> int:
        """Generate port for proxy.

        Args:
            user: Username
            proxy_name: Proxy name

        Returns:
            Generated port number
        """
        # Simple hash-based generation for demo
        import hashlib
        base = f"{user}:{proxy_name}:port"
        hash_val = int(hashlib.md5(base.encode()).hexdigest()[:8], 16)
        return 40000 + (hash_val % 10000)

    def _generate_uuid(self, user: str, proxy_name: str) -> str:
        """Generate UUID for proxy.

        Args:
            user: Username
            proxy_name: Proxy name

        Returns:
            Generated UUID
        """
        import hashlib
        import uuid
        
        base = f"{user}:{proxy_name}:uuid"
        hash_val = hashlib.md5(base.encode()).hexdigest()
        
        # Convert to UUID format
        return str(uuid.UUID(hash_val))

    def _generate_obfs_password(self, user: str, proxy_name: str) -> str:
        """Generate obfs password for proxy.

        Args:
            user: Username
            proxy_name: Proxy name

        Returns:
            Generated obfs password
        """
        import hashlib
        base = f"{user}:{proxy_name}:obfs"
        return hashlib.md5(base.encode()).hexdigest()[:10]

    def get_proxy_list(self) -> List[str]:
        """Get list of proxy names for PROXY_LIST.

        Returns:
            List of proxy names
        """
        proxy_configs = self.generate_proxy_configs()
        return [config['name'] for config in proxy_configs]
