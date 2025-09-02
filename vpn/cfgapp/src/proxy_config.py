"""Proxy configuration management and generation."""

import base64
import io
import json
import logging
import urllib.parse
from pathlib import Path
from typing import Any

import qrcode
from qrcode.image.pil import PilImage

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

    def _load_config(self) -> dict[str, Any]:
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
            with open(self.config_path, encoding="utf-8") as f:
                config = json.load(f)
            logger.info(f"Loaded proxy config from {self.config_path}")
            return config
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in proxy config file: {e}")
            raise

    def get_users(self) -> list[str]:
        """Get list of users from configuration.

        Returns:
            List of user names
        """
        return self.config_data.get("users", [])

    def get_subs(self) -> dict[str, Any]:
        """Get subscriptions configuration.

        Returns:
            Subscriptions configuration
        """
        return self.config_data.get("subs", {})

    def get_subscription_proxies(self, sub_name: str | None = None) -> dict[str, Any]:
        """Get proxies for specific subscription.

        Args:
            sub_name: Subscription name, defaults to 'default'

        Returns:
            Dictionary of proxy configurations for the subscription
        """
        subs = self.get_subs()
        if not sub_name:
            sub_name = "default"

        if sub_name not in subs:
            logger.warning(f"Subscription '{sub_name}' not found, using 'default'")
            sub_name = "default"

        return subs.get(sub_name, {})

    def generate_proxy_configs(
        self,
        sub_name: str | None = None,
        password: str | None = None,
        user: str | None = None,
    ) -> list[dict[str, Any]]:
        """Generate proxy configurations for all protocols in subscription.

        Args:
            sub_name: Subscription name, defaults to 'default'
            password: Password from query parameter (optional)
            user: Username for authentication (optional)

        Returns:
            List of proxy configurations (one per proxy in subscription)
        """
        proxy_configs = []
        subscription_proxies = self.get_subscription_proxies(sub_name)

        for proxy_name, proxy_config in subscription_proxies.items():
            protocol = proxy_config.get("protocol", "")
            host = proxy_config.get("host", "")

            if not protocol or not host:
                logger.warning(f"Invalid proxy config: {proxy_name}")
                continue

            # Generate one config per proxy (not per user)
            proxy_config = self._generate_proxy_config(
                protocol, host, proxy_name, password, user
            )
            if proxy_config:
                proxy_configs.append(proxy_config)

        logger.info(
            f"Generated {len(proxy_configs)} proxy configurations for subscription '{sub_name or 'default'}'"
        )
        return proxy_configs

    def _generate_proxy_config(
        self,
        protocol: str,
        host: str,
        proxy_name: str,
        password: str | None = None,
        user: str | None = None,
    ) -> dict[str, Any]:
        """Generate proxy configuration for specific protocol.

        Args:
            protocol: Proxy protocol (e.g., 'hy2', 'hy2-v2', 'vmess', etc.)
            host: Proxy host
            proxy_name: Proxy name
            password: Password from query parameter (optional)
            user: Username for authentication (optional)

        Returns:
            Proxy configuration dictionary
        """
        if protocol == "hy2":
            return self._generate_hysteria2_config(host, proxy_name, password)
        elif protocol == "hy2-v2":
            return self._generate_hysteria2_v2_config(host, proxy_name, password, user)
        elif protocol == "vmess":
            return self._generate_vmess_config(host, proxy_name)
        elif protocol == "vless":
            return self._generate_vless_config(host, proxy_name, user)
        else:
            logger.warning(f"Unsupported protocol: {protocol}")
            return {}

    def _generate_hysteria2_config(
        self, host: str, proxy_name: str, password: str | None = None
    ) -> dict[str, Any]:
        """Generate Hysteria2 proxy configuration.

        Args:
            host: Proxy host
            proxy_name: Proxy name
            password: Password from query parameter (optional)

        Returns:
            Hysteria2 configuration dictionary
        """
        # Generate unique name
        name = f"{proxy_name}"

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
            "udp": True,
        }

    def _generate_hysteria2_v2_config(
        self,
        host: str,
        proxy_name: str,
        password: str | None = None,
        user: str | None = None,
    ) -> dict[str, Any]:
        """Generate Hysteria2 v2 proxy configuration.

        Args:
            host: Proxy host
            proxy_name: Proxy name
            password: Password from query parameter (optional)
            user: Username for authentication (optional)

        Returns:
            Hysteria2 v2 configuration dictionary
        """
        # Generate unique name
        name = f"{proxy_name}"

        # Use provided password or generate one
        if password:
            # For hy2-v2 in Clash configs, use user:password format if user is provided
            if user:
                proxy_password = f"{user}:{password}"
            else:
                proxy_password = password
        else:
            proxy_password = self._generate_password(proxy_name)

        port = settings.hysteria2_v2_port  # Use v2 port from environment variable

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
            "udp": True,
        }

    def _generate_vmess_config(self, host: str, proxy_name: str) -> dict[str, Any]:
        """Generate VMess proxy configuration.

        Args:
            host: Proxy host
            proxy_name: Proxy name

        Returns:
            VMess configuration dictionary
        """
        name = f"{proxy_name}"
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
            "udp": True,
        }

    def _generate_vless_config(
        self, host: str, proxy_name: str, user: str | None = None
    ) -> dict[str, Any]:
        """Generate VLESS proxy configuration.

        Args:
            host: Proxy host
            proxy_name: Proxy name
            user: Username for authentication (optional)

        Returns:
            VLESS configuration dictionary
        """
        name = f"{proxy_name}"

        # Generate UUID based on user + salt (same as server config)
        if user:
            import hashlib

            base = f"{user}.{settings.salt}"
            hash_val = hashlib.sha256(base.encode()).hexdigest()
            # Convert to UUID format (8-4-4-4-12)
            uuid = f"{hash_val[:8]}-{hash_val[8:12]}-{hash_val[12:16]}-{hash_val[16:20]}-{hash_val[20:32]}"
        else:
            uuid = self._generate_uuid(proxy_name)

        port = settings.https_port  # Use HTTPS port for client routing

        return {
            "name": name,
            "type": "vless",
            "server": host,
            "port": port,
            "uuid": uuid,
            "network": "grpc",
            "grpc-opts": {"grpc-service-name": "grpc"},
            "security": "reality",
            "reality-opts": {
                "public-key": settings.reality_public_key
                if hasattr(settings, "reality_public_key")
                else "",
                "short-id": settings.reality_short_id,
                "server-name": "www.microsoft.com",
            },
            "udp": True,
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

    def get_proxy_list(
        self, sub_name: str | None = None, password: str | None = None
    ) -> list[str]:
        """Get list of proxy names for PROXY_LIST.

        Args:
            sub_name: Subscription name, defaults to 'default'
            password: Password from query parameter (optional)

        Returns:
            List of proxy names
        """
        proxy_configs = self.generate_proxy_configs(sub_name, password, None)
        return [config["name"] for config in proxy_configs]

    def generate_shadowrocket_subscription(
        self,
        sub_name: str | None = None,
        password: str | None = None,
        user: str | None = None,
    ) -> str:
        """Generate ShadowRocket subscription URLs.

        Args:
            sub_name: Subscription name, defaults to 'default'
            password: Password from query parameter (optional)
            user: Username for authentication (optional)

        Returns:
            Base64 encoded subscription URLs
        """
        proxy_configs = self.generate_proxy_configs(sub_name, password, user)
        urls = []

        for config in proxy_configs:
            protocol = config.get("type", "")
            if protocol == "hysteria2":
                # Check if this is hy2-v2 by looking at the port
                if config.get("port") == settings.hysteria2_v2_port:
                    # For hy2-v2, create user:password format
                    user_password = (
                        f"{user}:{password}" if user and password else password
                    )
                    url = self._generate_hysteria2_v2_url(config, user_password)
                else:
                    url = self._generate_hysteria2_url(config)
            elif protocol == "vmess":
                url = self._generate_vmess_url(config)
            elif protocol == "vless":
                url = self._generate_vless_url(config)
            else:
                logger.warning(f"Unsupported protocol for ShadowRocket: {protocol}")
                continue

            if url:
                urls.append(url)

        # Join URLs with newlines and encode to base64
        subscription_content = "\n".join(urls)
        return base64.b64encode(subscription_content.encode()).decode()

    def _generate_hysteria2_url(self, config: dict[str, Any]) -> str:
        """Generate Hysteria2 URL for ShadowRocket.

        Args:
            config: Hysteria2 configuration

        Returns:
            Hysteria2 URL string
        """
        password = config["password"]
        server = config["server"]
        port = config["port"]
        name = config["name"]

        # Build query parameters
        params = {
            "peer": "i.am.com",
            "insecure": "1",
            "alpn": "h3",
            "obfs": "salamander",
            "obfs-password": config["obfs-password"],
            "udp": "1",
            "fragment": "1,40-60,30-50",
        }

        query_string = urllib.parse.urlencode(params)
        return f"hysteria2://{password}@{server}:{port}?{query_string}#{name}"

    def _generate_hysteria2_v2_url(
        self, config: dict[str, Any], user_password: str | None = None
    ) -> str:
        """Generate Hysteria2 v2 URL for ShadowRocket with user:password format.

        Args:
            config: Hysteria2 v2 configuration
            user_password: User password in format "user:password" (optional)

        Returns:
            Hysteria2 v2 URL string
        """
        password = config["password"]
        server = config["server"]
        port = config["port"]
        name = config["name"]

        # For hy2-v2, use user:password format if user_password is provided
        if user_password and ":" in user_password:
            # user_password is already in "user:password" format
            auth_password = user_password
        else:
            # Fallback to regular password
            auth_password = password

        # Build query parameters
        params = {
            "peer": "i.am.com",
            "insecure": "1",
            "alpn": "h3",
            "obfs": "salamander",
            "obfs-password": config["obfs-password"],
            "udp": "1",
            "fragment": "1,40-60,30-50",
        }

        query_string = urllib.parse.urlencode(params)
        return f"hysteria2://{auth_password}@{server}:{port}?{query_string}#{name}"

    def _generate_vmess_url(self, config: dict[str, Any]) -> str:
        """Generate VMess URL for ShadowRocket.

        Args:
            config: VMess configuration

        Returns:
            VMess URL string
        """
        # Create VMess configuration JSON
        vmess_config = {
            "v": "2",
            "ps": config["name"],
            "add": config["server"],
            "port": str(config["port"]),
            "id": config["uuid"],
            "aid": "0",
            "net": "ws",
            "type": "none",
            "host": "",
            "path": "/ws",
            "tls": "tls",
            "fragment": "1,40-60,30-50",
        }

        # Encode to base64
        config_json = json.dumps(vmess_config, separators=(",", ":"))
        config_b64 = base64.b64encode(config_json.encode()).decode()

        return f"vmess://{config_b64}?fragment=1,40-60,30-50"

    def _generate_vless_url(self, config: dict[str, Any]) -> str:
        """Generate VLESS URL for ShadowRocket.

        Args:
            config: VLESS configuration

        Returns:
            VLESS URL string
        """
        uuid = config["uuid"]
        server = config["server"]
        port = config["port"]
        name = config["name"]

        # Build query parameters for Reality protocol
        params = {
            "remarks": name,
            "tls": "1",
            "peer": "www.microsoft.com",
            "alpn": "h2,http/1.1",
            "xtls": "2",
            "pbk": settings.reality_public_key
            if hasattr(settings, "reality_public_key")
            else "",
            "sid": settings.reality_short_id,
        }

        query_string = urllib.parse.urlencode(params)
        return f"vless://{uuid}@{server}:{port}?{query_string}"

    def generate_subscription_url(
        self,
        base_url: str,
        user: str,
        sub_name: str | None = None,
        password: str | None = None,
    ) -> str:
        """Generate sub:// URL for subscription.

        Args:
            base_url: Base URL of the application
            user: Username for authentication
            sub_name: Subscription name, defaults to 'default'
            password: Password from query parameter (optional)

        Returns:
            sub:// URL string
        """
        # Build the /sr endpoint URL with parameters
        sr_url = f"{base_url}/sr"
        params = {"u": user}  # User is required for authentication

        if sub_name:
            params["sub"] = sub_name
        if password:
            params["hash"] = password

        query_string = urllib.parse.urlencode(params)
        sr_url = f"{sr_url}?{query_string}"

        # Encode the URL to base64
        sr_url_b64 = base64.b64encode(sr_url.encode()).decode()

        # Create sub:// URL with subscription name fragment
        subscription_name = sub_name or "default"
        return f"sub://{sr_url_b64}?udp=1&allowInsecure=1#{subscription_name}"

    def generate_qr_code(self, data: str) -> str:
        """Generate QR code image as base64 string.

        Args:
            data: Data to encode in QR code

        Returns:
            Base64 encoded PNG image
        """
        # Create QR code
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_L,
            box_size=10,
            border=4,
        )
        qr.add_data(data)
        qr.make(fit=True)

        # Create image
        img = qr.make_image(
            fill_color="black", back_color="white", image_factory=PilImage
        )

        # Convert to base64
        buffer = io.BytesIO()
        img.save(buffer, format="PNG")
        buffer.seek(0)
        img_b64 = base64.b64encode(buffer.getvalue()).decode()

        return img_b64
