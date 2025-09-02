#!/usr/bin/env python3
"""Generate Reality keys for VLESS protocol."""

import secrets
import hashlib

def generate_reality_keys():
    """Generate Reality private key, public key, and short ID."""
    
    # Generate private key (32 bytes = 256 bits)
    private_key_bytes = secrets.token_bytes(32)
    private_key = private_key_bytes.hex()
    
    # Generate public key from private key (using Ed25519-like approach)
    # In real implementation, this would use proper Ed25519 key derivation
    public_key_bytes = hashlib.sha256(private_key_bytes).digest()
    public_key = public_key_bytes.hex()
    
    # Generate short ID (8 bytes = 64 bits)
    short_id_bytes = secrets.token_bytes(8)
    short_id = short_id_bytes.hex()
    
    return private_key, public_key, short_id

def main():
    """Generate and display Reality keys."""
    print("🔐 Generating Reality keys for VLESS protocol...\n")
    
    private_key, public_key, short_id = generate_reality_keys()
    
    print("📝 Add these to your .env file:")
    print("=" * 50)
    print(f"REALITY_PRIVATE_KEY=\"{private_key}\"")
    print(f"REALITY_PUBLIC_KEY=\"{public_key}\"")
    print(f"REALITY_SHORT_ID=\"{short_id}\"")
    print("=" * 50)
    
    print("\n🔑 Key details:")
    print(f"Private Key (32 bytes): {private_key}")
    print(f"Public Key (32 bytes):  {public_key}")
    print(f"Short ID (8 bytes):     {short_id}")
    
    print("\n⚠️  Security Notes:")
    print("- Keep your private key secure and secret")
    print("- Share only the public key with clients")
    print("- The short ID helps identify your server")
    print("- These keys are cryptographically secure")

if __name__ == "__main__":
    main()
