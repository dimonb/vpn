#!/usr/bin/env python3
"""Test environment variables in cfgapp."""

import os

def main():
    """Check environment variables."""
    print("🔍 Environment variables in cfgapp:")
    print(f"REALITY_PRIVATE_KEY: {os.environ.get('REALITY_PRIVATE_KEY', 'NOT SET')}")
    print(f"REALITY_PUBLIC_KEY: {os.environ.get('REALITY_PUBLIC_KEY', 'NOT SET')}")
    print(f"REALITY_SHORT_ID: {os.environ.get('REALITY_SHORT_ID', 'NOT SET')}")
    print(f"VLESS_PORT: {os.environ.get('VLESS_PORT', 'NOT SET')}")
    print(f"SALT: {os.environ.get('SALT', 'NOT SET')}")

if __name__ == "__main__":
    main()
