#!/usr/bin/env python3
"""Test real VLESS Reality configuration generation."""

import os
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

def test_reality_generation():
    """Test Reality configuration generation."""
    
    try:
        from proxy_config import ProxyConfig
        
        # Create test config
        test_config = {
            "users": ["dimonb"],
            "subs": {
                "reality": {
                    "RU_0_YANDEX": {
                        "protocol": "vless",
                        "host": "ru-1.yandex.v.dimonb.com"
                    }
                }
            }
        }
        
        # Write test config to file
        config_file = "test_reality_gen.json"
        import json
        with open(config_file, 'w') as f:
            json.dump(test_config, f)
        
        # Test configuration generation
        proxy_config = ProxyConfig(config_file)
        
        print("🔧 Testing VLESS Reality config generation...")
        vless_config = proxy_config._generate_vless_config(
            "ru-1.yandex.v.dimonb.com", "RU_0_YANDEX", "dimonb"
        )
        
        print("\n📋 Generated VLESS Reality config:")
        for key, value in vless_config.items():
            print(f"  {key}: {value}")
        
        # Test URL generation
        print("\n🔗 Testing VLESS Reality URL generation...")
        vless_url = proxy_config._generate_vless_url(
            "ru-1.yandex.v.dimonb.com", "8443", "dimonb", "RU_0_YANDEX"
        )
        print(f"Generated URL: {vless_url}")
        
        # Clean up
        os.remove(config_file)
        
        print("\n✅ Reality configuration generation test completed successfully!")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_reality_generation()
