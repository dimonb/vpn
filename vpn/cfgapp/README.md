# CFG App

Python application for proxy rule processing and NETSET expansion, designed to work as a Cloudflare Worker replacement.

## Features

- **Template Processing**: Process templates with RULE-SET and NETSET expansion
- **Authentication**: Built-in authentication system
- **Clash Support**: Full Clash YAML configuration processing
- **Proxy Configuration**: Dynamic proxy generation from JSON configuration
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
      "US_1_VULTR": {"protocol": "vmess", "host": "us-1.vultr.v.dimonb.com"},
      "SG_1_LINODE": {"protocol": "vless", "host": "sg-1.linode.v.dimonb.com"}
    }
  }
}
```

#### Supported Protocols

- **hy2**: Hysteria2 protocol
- **vmess**: VMess protocol  
- **vless**: VLESS protocol

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

## Installation

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
- `GET /{path:path}` - Main proxy handler for all other requests

## Template Tags

- `#CLASH` - Process as Clash YAML configuration
- `#AUTH` - Require authentication for the template
- `#SHADOWROCKET` - Process as Shadowrocket configuration

## License

MIT License



