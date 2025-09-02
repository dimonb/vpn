#!/usr/bin/env python3
"""Test script for VLESS Reality configuration generation."""

import os
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from proxy_config import ProxyConfig

# Set environment variables for testing
os.environ["VLESS_PORT"] = "8443"
os.environ["REALITY_PRIVATE_KEY"] = "test-private-key"
os.environ["REALITY_PUBLIC_KEY"] = "test-public-key"
os.environ["REALITY_SHORT_ID"] = "c047f3e99c90ff71"
os.environ["SALT"] = "test-salt"

def main():
    """Test VLESS Reality configuration generation."""
    config_file = "test_reality_config.json"
    
    if not Path(config_file).exists():
        print(f"Error: {config_file} not found")
        return
    
    try:
        proxy_config = ProxyConfig(config_file)
        
        # Test VLESS config generation
        print("=== VLESS Reality Configuration ===")
        vless_config = proxy_config._generate_vless_config(
            "ru-1.yandex.v.dimonb.com", "RU_0_YANDEX", "dimonb"
        )
        
        print("Generated config:")
        for key, value in vless_config.items():
            print(f"  {key}: {value}")
        
        # Test URL generation
        print("\n=== VLESS Reality URL ===")
        vless_url = proxy_config._generate_vless_url(
            "ru-1.yandex.v.dimonb.com", "8443", "dimonb", "RU_0_YANDEX"
        )
        print(f"Generated URL: {vless_url}")
        
        # Test subscription generation
        print("\n=== ShadowRocket Subscription ===")
        subscription = proxy_config.generate_shadowrocket_subscription(
            "dimonb", "test-hash", "reality"
        )
        print(f"Subscription URL: {subscription}")
        
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
