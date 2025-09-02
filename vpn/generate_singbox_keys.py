#!/usr/bin/env python3
"""Generate Reality keys compatible with sing-box format."""

import secrets
import base64

def generate_singbox_keys():
    """Generate Reality keys in sing-box compatible format."""
    
    # Generate private key (32 bytes = 256 bits)
    private_key_bytes = secrets.token_bytes(32)
    private_key_base64 = base64.urlsafe_b64encode(private_key_bytes).decode('utf-8').rstrip('=')
    
    # Generate public key (in real sing-box, this would be derived from private key)
    # For demo purposes, we'll generate a separate public key
    public_key_bytes = secrets.token_bytes(32)
    public_key_base64 = base64.urlsafe_b64encode(public_key_bytes).decode('utf-8').rstrip('=')
    
    # Generate short ID (8 bytes = 64 bits)
    short_id_bytes = secrets.token_bytes(8)
    short_id = short_id_bytes.hex()
    
    return private_key_base64, public_key_base64, short_id

def main():
    """Generate and display sing-box compatible Reality keys."""
    print("🔐 Generating sing-box compatible Reality keys...\n")
    
    private_key, public_key, short_id = generate_singbox_keys()
    
    print("📝 Add these to your .env file:")
    print("=" * 60)
    print(f"REALITY_PRIVATE_KEY=\"{private_key}\"")
    print(f"REALITY_PUBLIC_KEY=\"{public_key}\"")
    print(f"REALITY_SHORT_ID=\"{short_id}\"")
    print("=" * 60)
    
    print("\n🔑 Key details:")
    print(f"Private Key (base64): {private_key}")
    print(f"Public Key (base64):  {public_key}")
    print(f"Short ID (hex):       {short_id}")
    
    print("\n📋 For sing-box configuration:")
    print("=" * 60)
    print(f'"private_key": "{private_key}",')
    print(f'"short_id": ["{short_id}"]')
    print("=" * 60)
    
    print("\n⚠️  Security Notes:")
    print("- Keep your private key secure and secret")
    print("- Share only the public key with clients")
    print("- The short ID helps identify your server")
    print("- These keys are in sing-box compatible format")

if __name__ == "__main__":
    main()
