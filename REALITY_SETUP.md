# VLESS Reality Setup Guide

## Overview
VLESS Reality is a protocol that uses real TLS certificates from legitimate websites (like Google) to establish connections, making traffic appear as normal HTTPS traffic.

## Configuration

### 1. Environment Variables
Add these to your `.env` file:

```bash
# Reality Configuration
REALITY_PRIVATE_KEY="your-reality-private-key-here"
REALITY_PUBLIC_KEY="your-reality-public-key-here"
REALITY_SHORT_ID="c047f3e99c90ff71"
VLESS_PORT="443"
```

### 2. Generate Reality Keys
You can generate Reality keys using sing-box:

```bash
# Generate private key
sing-box generate reality-keypair

# Or use existing keys from your Reality server
```

### 3. Server Configuration
The server will be configured with:
- **Port**: 443 (standard HTTPS port)
- **Server Name**: www.microsoft.com
- **Handshake Server**: www.microsoft.com:443
- **Transport**: gRPC with service name "grpc"

### 4. Client Configuration
Clients will receive VLESS URLs with:
- **Security**: reality (instead of tls)
- **SNI**: www.microsoft.com
- **Fingerprint**: chrome
- **Public Key**: from REALITY_PUBLIC_KEY
- **Short ID**: from REALITY_SHORT_ID

## Example Configuration

### Server (sing-box.json)
```json
{
  "type": "vless",
  "tag": "vless-in",
  "listen": "0.0.0.0",
  "listen_port": 443,
  "users": [
    {
      "name": "dimonb",
      "uuid": "generated-uuid",
      "flow": ""
    }
  ],
  "tls": {
    "enabled": true,
    "alpn": ["h2", "http/1.1"],
    "server_name": "www.microsoft.com",
    "reality": {
      "enabled": true,
      "handshake": {
        "server": "www.microsoft.com:443",
        "server_port": 443
      },
      "private_key": "your-private-key",
      "short_id": ["c047f3e99c90ff71"]
    }
  },
  "transport": {
    "type": "grpc",
    "service_name": "grpc"
  }
}
```

### Client (ShadowRocket)
```
vless://uuid@13.60.43.17:443?type=grpc&serviceName=grpc&security=reality&sni=www.microsoft.com&fp=chrome&pbk=public-key&sid=c047f3e99c90ff71&fragment=1,40-60,30-50#SE_1_REALITY
```

## Benefits
1. **Stealth**: Traffic appears as normal HTTPS to Google
2. **No Certificate Management**: Uses real Google certificates
3. **DPI Evasion**: Hard to detect and block
4. **High Performance**: gRPC transport with Reality

## Security Notes
- Keep your private key secure
- Use strong UUIDs for each user
- Consider rotating keys periodically
- Monitor for unusual traffic patterns
