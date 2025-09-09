#!/usr/bin/env python3
"""Test VLESS Reality URL format."""

import os
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

def test_url_format():
    """Test that VLESS Reality URL is generated in correct format."""
    
    try:
        from proxy_config import ProxyConfig
        
        # Create test config
        test_config = {
            "users": ["dimonb"],
            "subs": {
                "reality": {
                    "RU_0_YANDEX": {
                        "protocol": "vless",
                        "host": "ru-0.yandex.v.dimonb.com"
                    }
                }
            }
        }
        
        # Write test config to file
        config_file = "test_url_format.json"
        import json
        with open(config_file, 'w') as f:
            json.dump(test_config, f)
        
        # Test configuration generation
        proxy_config = ProxyConfig(config_file)
        
        print("🔧 Testing VLESS Reality URL format...")
        vless_url = proxy_config._generate_vless_url(
            "ru-0.yandex.v.dimonb.com", "8443", "dimonb", "RU_0_YANDEX"
        )
        
        print(f"\n📋 Generated URL: {vless_url}")
        
        # Check URL format
        expected_parts = [
            "vless://",
            "ru-0.yandex.v.dimonb.com:8443",
            "remarks=RU_0_YANDEX",
            "tls=1",
            "peer=ok.ru",
            "alpn=h2,http/1.1",
            "xtls=2",
            "pbk=",
            "sid="
        ]
        
        print("\n✅ Checking URL format...")
        for part in expected_parts:
            if part in vless_url:
                print(f"  ✓ {part}")
            else:
                print(f"  ✗ {part} - NOT FOUND")
        
        # Clean up
        os.remove(config_file)
        
        print("\n✅ URL format test completed!")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_url_format()
