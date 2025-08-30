# CFG App

Python application for proxy rule processing and NETSET expansion, designed to work as a Cloudflare Worker replacement.

## Features

- **Template Processing**: Process templates with RULE-SET and NETSET expansion
- **Authentication**: Built-in authentication system
- **Clash Support**: Full Clash YAML configuration processing
- **Proxy Configuration**: Dynamic proxy generation from JSON configuration
- **Subscription Support**: Multiple subscription tiers with query parameter selection
- **IP Aggregation**: Smart IP block aggregation and deduplication

## Configuration

### Environment Variables

Create a `.env` file based on `env.example`:

```bash
# API Configuration
CONFIG_HOST=shadowrocket.ebac.dev
API_HOST=shadowrocket.ebac.dev

# Authentication
SALT=your-secret-salt-here

# IP Aggregation Settings
IPV4_BLOCK_PREFIX=18
IPV6_BLOCK_PREFIX=32

# Server Configuration
HOST=0.0.0.0
PORT=8000

# Proxy Configuration
PROXY_CONFIG=/path/to/proxy_config.json
OBFS_PASSWORD=your-obfs-password-here
HYSTERIA2_PORT=47012
BASE_URL=https://your-domain.com

# Logging
LOG_LEVEL=INFO
```

### Proxy Configuration

The `PROXY_CONFIG` environment variable should point to a JSON file with the following structure:

```json
{
  "users": [
    "dimonb",
    "diakon", 
    "ivan",
    "petrov"
  ],
  "subs": {
    "default": {
      "DE_1_CONTABO": {"protocol": "hy2", "host": "de-1.contabo.v.dimonb.com"},
      "US_1_VULTR": {"protocol": "vmess", "host": "us-1.vultr.v.dimonb.com"}
    },
    "premium": {
      "SG_1_LINODE": {"protocol": "vless", "host": "sg-1.linode.v.dimonb.com"}
    }
  }
}
```

#### Supported Protocols

- **hy2**: Hysteria2 protocol
- **vmess**: VMess protocol  
- **vless**: VLESS protocol

#### Subscription Selection

- **Default**: Uses `subs.default` if no query parameter is provided
- **Custom**: Use query parameter `?sub=premium` to select specific subscription
- **Fallback**: If specified subscription doesn't exist, falls back to `default`

#### Proxy Generation Logic

The system generates **one proxy configuration per proxy entry** in the subscription, not per user. Users are used for generating unique parameters (passwords, ports, UUIDs) but the final configuration contains one proxy per subscription entry.

#### Environment Variables for Proxy Configuration

- **OBFS_PASSWORD**: Password for obfs (obfuscation) in Hysteria2 protocol
- **HYSTERIA2_PORT**: Fixed port number for Hysteria2 proxies (default: 47012)
- **BASE_URL**: Base URL for subscription generation (e.g., https://your-domain.com). If not set, the system will use the request host as fallback

#### Password Configuration

The system supports two password modes for Hysteria2 proxies:

1. **Generated Password**: If no `hash` query parameter is provided, the system generates a deterministic password based on the proxy name
2. **Custom Password**: If `hash` query parameter is provided, it will be used as the password for Hysteria2 proxies

Example:
- `GET /clash.tpl` - Uses generated password
- `GET /clash.tpl?hash=30dfb07872c73a324ec6692a00872e5cd1f4d99ee2c4a0a9d210ea7b8a1d48e6` - Uses provided password

## Clash Configuration

The app supports Clash YAML templates with special placeholders:

### PROXY_CONFIGS

Replace with generated proxy configurations:

```yaml
proxies:
  - PROXY_CONFIGS
```

### PROXY_LIST

Replace with list of proxy names:

```yaml
proxy-groups:
  - name: PROXY
    type: url-test
    url: http://www.gstatic.com/generate_204
    interval: 600
    tolerance: 100
    proxies:
      - PROXY_LIST
```

### RULE-SET Expansion

RULE-SET entries are expanded in the order they appear in the template, preserving the original rule order:

```yaml
rules:
  - DOMAIN-SUFFIX,example.com,PROXY
  - RULE-SET,https://s.dimonb.com/lists/google.list,PROXY
  - DOMAIN-SUFFIX,test.com,PROXY
  - RULE-SET,https://s.dimonb.com/lists/youtube.list,PROXY
  - MATCH,DIRECT
```

After expansion, the rules maintain their relative order:
```yaml
rules:
  - DOMAIN-SUFFIX,example.com,PROXY
  - DOMAIN-SUFFIX,google.com,PROXY
  - DOMAIN-SUFFIX,googleapis.com,PROXY
  - DOMAIN-SUFFIX,test.com,PROXY
  - DOMAIN-SUFFIX,youtube.com,PROXY
  - DOMAIN-SUFFIX,ytimg.com,PROXY
  - MATCH,DIRECT
```

### Example Clash Template

```yaml
#CLASH,AUTH

mixed-port: 7890
allow-lan: true
mode: Rule
log-level: info

dns:
  enable: true
  listen: 0.0.0.0:1053
  enhanced-mode: fake-ip
  nameserver:
    - https://1.1.1.1/dns-query
    - https://8.8.8.8/dns-query

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
  - RULE-SET,https://s.dimonb.com/lists/google.list,PROXY
  - MATCH,DIRECT
```

### Generated Proxy Configuration

The system generates proxy configurations with the following structure:

#### Hysteria2
```yaml
- name: de_1_contabo
  type: hysteria2
  server: de-1.contabo.v.dimonb.com
  port: 47012
  password: bd827d918fab8f0baab41e8f785c52203f829f45f8e9de3467ba97d9e09bdff8
  sni: i.am.com
  skip-cert-verify: true
  alpn: ["h3"]
  up: 50
  down: 200
  obfs: salamander
  obfs-password: iHWnSdFq8MKT9AdBN5uu
  fast-open: true
  udp: true
```

#### VMess
```yaml
- name: us_1_vultr
  type: vmess
  server: us-1.vultr.v.dimonb.com
  port: 47970
  uuid: 5e284f0f-f2c2-3a95-2197-41e478d9f8cf
  alterId: 0
  cipher: auto
  tls: true
  servername: us-1.vultr.v.dimonb.com
  skip-cert-verify: true
  udp: true
```

## Usage Examples

### Default Subscription
```
GET /clash.tpl
```

### Premium Subscription
```
GET /clash.tpl?sub=premium
```

### With Authentication
```
GET /clash.tpl?sub=premium&u=dimonb&hash=abc123...
```

### With Custom Password
```
GET /clash.tpl?hash=30dfb07872c73a324ec6692a00872e5cd1f4d99ee2c4a0a9d210ea7b8a1d48e6
```

### Combined Parameters
```
GET /clash.tpl?sub=premium&hash=30dfb07872c73a324ec6692a00872e5cd1f4d99ee2c4a0a9d210ea7b8a1d48e6
```

### ShadowRocket Subscription
```
GET /sr?u=dimonb&hash=valid_hash
GET /sr?u=dimonb&hash=valid_hash&sub=premium
GET /sr?u=dimonb&hash=custom_password&sub=default
```

### Authentication Failure Cases

- User not in PROXY_CONFIG users list
- Invalid hash calculation
- Missing user or hash parameters

## ShadowRocket Subscription

The application provides a dedicated endpoint `/sr` for ShadowRocket subscription generation.

### Features

- **Base64 Encoded**: Returns base64-encoded subscription content
- **Multiple Protocols**: Supports Hysteria2, VMess, and VLESS protocols
- **Authentication Required**: Uses the same authentication system as templates
- **Subscription Support**: Works with multiple subscriptions (default, premium, etc.)
- **Custom Passwords**: Supports custom passwords via `hash` parameter

### URL Formats

#### Hysteria2
```
hysteria2://password@server:port?peer=i.am.com&insecure=1&alpn=h3&obfs=salamander&obfs-password=xxx&udp=1#name.hy2
```

#### VMess
```
vmess://base64_config?fragment=1,40-60,30-50
```

Where `base64_config` contains:
```json
{
  "v": "2",
  "ps": "proxy_name",
  "add": "server",
  "port": "port",
  "id": "uuid",
  "aid": "0",
  "net": "ws",
  "type": "none",
  "host": "",
  "path": "/ws",
  "tls": "tls",
  "fragment": "1,40-60,30-50"
}
```

#### VLESS
```
vless://uuid@server:port?type=ws&path=/ws&host=server&security=tls&sni=server#name
```

### Usage

1. **Import into ShadowRocket**: Copy the base64 response and import as subscription
2. **Automatic Updates**: ShadowRocket will periodically fetch updates from the endpoint
3. **Authentication**: Each request requires valid user authentication

## Subscription Page

The application provides a user-friendly web page at `/sub` for easy subscription management.

### Features

- **🎨 Modern Design**: Beautiful responsive interface with gradient styling
- **📱 Mobile Optimized**: Works perfectly on iOS, Android, and desktop
- **📋 Smart Copy**: Advanced clipboard functionality with fallbacks for all devices
- **🔍 QR Code**: Auto-generated QR codes for instant mobile scanning
- **📖 Instructions**: Step-by-step guide for ShadowRocket setup
- **👤 User Info**: Displays current user and subscription details
- **🔐 Secure**: Same authentication system as other endpoints

### URL Format

The page generates `sub://` URLs in the correct format:
```
sub://<base64_encoded_sr_endpoint>?udp=1&allowInsecure=1
```

Where the base64 part contains the `/sr` endpoint URL with parameters.

### Usage Examples

```bash
# Basic usage
GET /sub?u=dimonb&hash=valid_hash

# With specific subscription
GET /sub?u=dimonb&hash=valid_hash&sub=premium

# With custom password
GET /sub?u=dimonb&hash=custom_password&sub=default
```

### Generated sub:// URL Format

The subscription page generates URLs that include the user authentication and subscription name:

```
sub://aHR0cHM6Ly9leGFtcGxlLmNvbS9zcj91PWRpbW9uYiZzdWI9ZGVmYXVsdA==?udp=1&allowInsecure=1#default
```

Which decodes to:
```
https://example.com/sr?u=dimonb&sub=default
```

The URL format is: `sub://<base64_sr_url>?udp=1&allowInsecure=1#<subscription_name>`
- Base64 part contains the `/sr` endpoint URL with authentication parameters
- Fragment (`#`) contains the subscription name for display in ShadowRocket
- Query parameters are ShadowRocket-specific settings

The user parameter (`u=username`) is automatically included to ensure proper authentication when ShadowRocket fetches the subscription.

### Mobile Compatibility

The page includes special handling for iOS Safari and mobile browsers:
- **iOS Safari**: Uses `document.execCommand` fallback
- **Modern browsers**: Uses `navigator.clipboard` API
- **Touch devices**: Auto-selects text on tap
- **Copy feedback**: Visual confirmation of successful copying

## Installation

### Local Development

1. Install dependencies:
```bash
poetry install
```

2. Set up environment variables:
```bash
cp env.example .env
# Edit .env with your configuration
```

3. Run the application:
```bash
poetry run python -m src.main
```

### Docker Deployment

#### Using Docker Compose (Recommended)

1. Create environment file:
```bash
cp env.example .env
# Edit .env with your configuration
```

2. Start the application:
```bash
docker-compose up -d
```

3. Check logs:
```bash
docker-compose logs -f cfgapp
```

4. Stop the application:
```bash
docker-compose down
```

#### Using Docker directly

1. Build the image:
```bash
docker build -t cfgapp .
```

2. Run the container:
```bash
docker run -d \
  --name cfgapp \
  -p 8000:8000 \
  -e BASE_URL=https://your-domain.com \
  -e PROXY_CONFIG=/app/config.json \
  -v /path/to/your/config.json:/app/config.json:ro \
  cfgapp
```

#### Docker Features

- **Multi-stage build**: Optimized image size by separating build and runtime dependencies
- **Non-root user**: Runs as unprivileged user for security
- **Health checks**: Built-in health monitoring
- **Template support**: Includes all templates and static files
- **Environment variables**: Full configuration through environment variables

## Development

### Running Tests

```bash
poetry run pytest tests/ -v
```

### Code Quality

```bash
poetry run ruff check src/ tests/
poetry run ruff format src/ tests/
```

## API Endpoints

- `GET /health` - Health check endpoint
- `GET /sr` - ShadowRocket subscription endpoint (requires authentication)
- `GET /sub` - Subscription page with QR code (requires authentication)
- `GET /{path:path}` - Main proxy handler for all other requests

## Template Tags

- `#CLASH` - Process as Clash YAML configuration
- `#AUTH` - Require authentication for the template
- `#SHADOWROCKET` - Process as Shadowrocket configuration

## License

MIT License
