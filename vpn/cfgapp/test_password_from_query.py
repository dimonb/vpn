#!/usr/bin/env python3
"""Test script for password from query parameter functionality."""

import json
import sys
import yaml
from pathlib import Path
from unittest.mock import AsyncMock

# Add src to path and set up for relative imports
sys.path.insert(0, str(Path(__file__).parent / "src"))
sys.path.insert(0, str(Path(__file__).parent))

# Import modules
from src.clash_processor import ClashProcessor
from src.proxy_config import ProxyConfig
from src.processor import TemplateProcessor


def main():
    """Main test function."""
    # Create test config
    test_config = {
        "users": ["dimonb", "diakon", "ivan", "petrov"],
        "subs": {
            "default": {
                "DE_1_CONTABO": {"protocol": "hy2", "host": "de-1.contabo.v.dimonb.com"}
            }
        }
    }
    
    # Write test config to file
    config_path = Path(__file__).parent / "test_config.json"
    with open(config_path, 'w') as f:
        json.dump(test_config, f, indent=2)
    
    try:
        # Mock settings for OBFS_PASSWORD and HYSTERIA2_PORT
        import src.config
        src.config.settings.obfs_password = "iHWnSdFq8MKT9AdBN5uu"
        src.config.settings.hysteria2_port = 47012
        
        # Load proxy config
        proxy_config = ProxyConfig(str(config_path))
        
        # Create mock template processor
        template_processor = AsyncMock(spec=TemplateProcessor)
        
        # Create clash processor
        clash_processor = ClashProcessor(template_processor, proxy_config)
        
        print("=== Password from Query Parameter Test ===\n")
        
        # Sample clash YAML with placeholders
        sample_yaml = """
mixed-port: 7890
allow-lan: true
mode: Rule
log-level: info

proxies:
  - PROXY_CONFIGS

proxy-groups:
  - name: PROXY
    type: url-test
    url: http://www.gstatic.com/generate_204
    interval: 600
    tolerance: 100
    proxies:
      - PROXY_LIST

rules:
  - DOMAIN-SUFFIX,whatismyipaddress.com,PROXY
  - MATCH,DIRECT
"""
        
        print("Original YAML:")
        print(sample_yaml)
        print("=" * 50)
        
        # Test 1: Without password (should generate one)
        print("Test 1: Without password parameter")
        clash_config = clash_processor.parse_clash_yaml(sample_yaml)
        request_headers = {}
        updated_config = clash_processor.replace_proxy_placeholders(clash_config, request_headers)
        
        print("Updated YAML (no password):")
        result_yaml = yaml.dump(updated_config, default_flow_style=False, allow_unicode=True, sort_keys=False)
        print(result_yaml)
        print("=" * 50)
        
        # Test 2: With password from query parameter
        print("Test 2: With password from query parameter")
        clash_config = clash_processor.parse_clash_yaml(sample_yaml)
        request_headers = {'x-query-string': 'hash=30dfb07872c73a324ec6692a00872e5cd1f4d99ee2c4a0a9d210ea7b8a1d48e6'}
        updated_config_with_password = clash_processor.replace_proxy_placeholders(clash_config, request_headers)
        
        print("Updated YAML (with password):")
        result_yaml_with_password = yaml.dump(updated_config_with_password, default_flow_style=False, allow_unicode=True, sort_keys=False)
        print(result_yaml_with_password)
        print("=" * 50)
        
        # Show differences
        print("Password comparison:")
        proxy_no_password = updated_config['proxies'][0]
        proxy_with_password = updated_config_with_password['proxies'][0]
        
        print(f"  Without hash parameter: {proxy_no_password['password']}")
        print(f"  With hash parameter:    {proxy_with_password['password']}")
        print(f"  Expected password:      30dfb07872c73a324ec6692a00872e5cd1f4d99ee2c4a0a9d210ea7b8a1d48e6")
        print(f"  Passwords match:        {proxy_with_password['password'] == '30dfb07872c73a324ec6692a00872e5cd1f4d99ee2c4a0a9d210ea7b8a1d48e6'}")
        
        print("\n✅ Password from query parameter test completed successfully!")
        return 0
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return 1
    finally:
        # Clean up test file
        if config_path.exists():
            config_path.unlink()


if __name__ == "__main__":
    sys.exit(main())
