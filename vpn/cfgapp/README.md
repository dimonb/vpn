# CFG App

Python application for proxy rule processing and NETSET expansion with support for multiple configuration formats and authentication.

## Features

- **Multiple Configuration Formats**: Support for CLASH YAML and SHADOWROCKET configurations
- **Authentication**: Optional authentication using query parameters with SHA256 hash verification
- **RULE-SET Expansion**: Automatic expansion of RULE-SET entries from remote URLs
- **NETSET Processing**: Support for NETSET files with IP aggregation
- **IP Aggregation**: IPv4/IPv6 CIDR block aggregation for optimized routing

## Configuration

### Environment Variables

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

# Logging
LOG_LEVEL=INFO
```

## Template Tags

Templates support tags in the first line to control processing behavior:

### Available Tags

- `#CLASH` - Process as CLASH YAML configuration
- `#SHADOWROCKET` - Process as SHADOWROCKET configuration (default)
- `#AUTH` - Require authentication via query parameters

### Examples

```yaml
#CLASH,AUTH
mixed-port: 7890
# ... rest of CLASH config
```

```ini
#SHADOWROCKET
[General]
# ... rest of Shadowrocket config
```

## Authentication

When `AUTH` tag is present, the application requires authentication via query parameters:

- `u=username` - Username
- `hash=sha256_hash` - SHA256 hash of `username.salt`

### Hash Calculation

```python
import hashlib

username = "testuser"
salt = "your-secret-salt"
hash_value = hashlib.sha256(f"{username}.{salt}".encode()).hexdigest()
```

### Example URL

```
https://example.com/config.tpl?u=testuser&hash=a1b2c3d4e5f6...
```

## RULE-SET Processing

The application automatically expands RULE-SET entries from remote URLs:

### CLASH Format

```yaml
rules:
  - RULE-SET,https://example.com/list.txt,PROXY
  - DOMAIN-SUFFIX,example.com,PROXY
```

### Shadowrocket Format

```ini
[Rule]
RULE-SET,https://example.com/list.txt,PROXY
DOMAIN-SUFFIX,example.com,PROXY
```

## NETSET Support

RULE-SET files can contain NETSET references:

```
#NETSET https://example.com/netset.txt
DOMAIN,example.com,PROXY
```

NETSET files are automatically fetched and expanded with IP aggregation.

## Development

### Installation

```bash
cd vpn/cfgapp
poetry install
```

### Running Tests

```bash
poetry run pytest tests/ -v
```

### Running the Application

```bash
poetry run python src/main.py
```

## API Endpoints

- `GET /health` - Health check
- `GET /{path}` - Main proxy handler for template processing

## Examples

See the `examples/` directory for template examples:

- `clash_with_auth.tpl` - CLASH configuration with authentication
- `shadowrocket.tpl` - Shadowrocket configuration



