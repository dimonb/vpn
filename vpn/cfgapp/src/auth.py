"""Authentication module for CFG application."""

import hashlib
from urllib.parse import parse_qs
from typing import Optional

from fastapi import HTTPException, Request

from .config import settings


def verify_auth(request: Request, proxy_config=None) -> bool:
    """Verify authentication using query parameters u and hash.

    Args:
        request: FastAPI request object
        proxy_config: Optional ProxyConfig instance for user validation

    Returns:
        True if authentication is valid, False otherwise

    Raises:
        HTTPException: If authentication fails
    """
    query_params = parse_qs(request.url.query)

    username = query_params.get('u', [None])[0]
    hash_param = query_params.get('hash', [None])[0]

    if not username or not hash_param:
        return False

    # Check if user exists in PROXY_CONFIG users list
    if proxy_config:
        users = proxy_config.get_users()
        if username not in users:
            return False

    # Calculate expected hash: sha256(username + '.' + salt)
    expected_hash = hashlib.sha256(f"{username}.{settings.salt}".encode()).hexdigest()

    if hash_param != expected_hash:
        return False

    return True


def require_auth(request: Request, proxy_config=None) -> None:
    """Require authentication and raise HTTPException if failed.

    Args:
        request: FastAPI request object
        proxy_config: Optional ProxyConfig instance for user validation

    Raises:
        HTTPException: If authentication fails
    """
    if not verify_auth(request, proxy_config):
        raise HTTPException(status_code=401, detail="Authentication required")


def extract_template_tags(template_content: str) -> list[str]:
    """Extract template tags from the first line of template content.

    Args:
        template_content: Template content as string

    Returns:
        List of tags found in the first line
    """
    lines = template_content.strip().split('\n')
    if not lines:
        return []

    first_line = lines[0].strip()
    if not first_line.startswith('#'):
        return []

    # Remove # and split by comma
    tags_part = first_line[1:].strip()
    if not tags_part:
        return []

    return [tag.strip() for tag in tags_part.split(',') if tag.strip()]


