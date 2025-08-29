# VPN Deploy — Automated VPN Server Deployment

A complete solution for deploying VPN servers using Ansible, Docker, and Sing-Box with automatic TLS certificate management via Caddy. Includes a Python-based configuration application for proxy rule processing and subscription management.

## 🚀 Features

- **Automated Deployment**: One-command deployment using Ansible
- **Docker-based**: Containerized VPN services for easy management
- **TLS Certificates**: Automatic HTTPS certificate generation with Caddy
- **User Management**: JSON-based user configuration with secure password generation
- **Subscription System**: Multi-tier subscription management with proxy configuration
- **CFG App**: Python application for proxy rule processing and NETSET expansion
- **Template Processing**: Support for Clash, Shadowrocket, and custom templates
- **QR Code Generation**: Easy client configuration sharing

## 📋 Requirements

### Local Machine
- `make` - Build automation tool
- `ansible` - Configuration management
- `ssh` - Secure shell client
- `jq` - JSON processor
- `sha256sum` (coreutils) or `shasum` - Hash utility
- `qrencode` - QR code generation (optional, for `make cn`)
- `poetry` - Python dependency management (for CFG App)

### Remote Servers
- Linux host with SSH access
- Docker and Docker Compose (installed automatically via `make install-docker`)

## 🛠️ Installation & Setup

### 1. Clone Repository
```bash
git clone <repository-url>
cd vpn
```

### 2. Configure Environment
Copy the environment template and set your secrets:
```bash
cp env.example .env
```

Edit `.env` file:
```bash
# VPN Configuration Secrets
SALT="your-secret-salt-here"
OBFS_PASSWORD="your-obfuscation-password"

# Port Configuration
HTTP_PORT="80"
HTTPS_PORT="443"
HYSTERIA2_PORT="47012"

# CFG App Configuration
CONFIG_HOST="your-config-host.com"
```

**Important**: 
- `SALT` is used for password hashing - keep it secret and consistent
- `OBFS_PASSWORD` is used for traffic obfuscation - use a strong password
- `CONFIG_HOST` is the hostname for configuration URLs

### 3. Configure Server Inventory
Copy the server configuration template:
```bash
cp servers.cfg.example servers.cfg
```

Edit `servers.cfg` with your server details:
```ini
[vpn]
de-1 ansible_host=your-server-ip-or-hostname

[vpn:vars]
ansible_user=root
ansible_python_interpreter=/usr/bin/python3
```

### 4. Configure Users and Subscriptions
Copy the configuration template:
```bash
cp config.json.example config.json
```

Edit `config.json` with your users and subscription configuration:
```json
{
  "users": [
    "user1",
    "user2",
    "user3"
  ],
  "subs": {
    "default": {
      "de_1_contabo": {"protocol": "hy2", "host": "de-1.contabo.v.dimonb.com"},
      "us_1_vultr": {"protocol": "vmess", "host": "us-1.vultr.v.dimonb.com"}
    },
    "premium": {
      "sg_1_linode": {"protocol": "vless", "host": "sg-1.linode.v.dimonb.com"}
    }
  }
}
```

**Supported Protocols**:
- `hy2`: Hysteria2 protocol
- `vmess`: VMess protocol
- `vless`: VLESS protocol

## 🚀 Deployment

### Install Docker (One-time Setup)
```bash
make install-docker
```

This command will:
- Install Docker and Docker Compose on all target servers
- Configure Docker service to start on boot

### Deploy VPN Services
```bash
make deploy
```

This command will:
- Validate environment configuration
- Deploy Sing-Box VPN server
- Configure Caddy for TLS certificates
- Set up Docker Compose services
- Generate user configurations

### Run CFG App (Development)
```bash
make cfgapp-dev
```

This runs the Python configuration application locally for development and testing.

## 🔧 Management Commands

### Generate User Passwords
```bash
make passwords
```

Output format:
```
user1: a1b2c3d4e5f6...
user2: f6e5d4c3b2a1...
```

### Generate QR Code for Client (Optional)
```bash
make cn NAME=username
```

This requires `qrencode` and will:
- Generate a QR code for the specified user
- Save it as `~/Downloads/username.png`
- Add the user to the VPN configuration if not exists

## 📁 Project Structure

```
vpn/
├── README.md              # This documentation
├── Makefile               # Build automation
├── deploy_vpn.yml         # Ansible deployment playbook
├── install_docker.yml     # Docker installation playbook
├── servers.cfg            # Server inventory (create from example)
├── servers.cfg.example    # Server inventory template
├── config.json            # User and subscription configuration
├── config.json.example    # Configuration template
├── .env                   # Environment secrets (create from example)
├── env.example            # Environment template
└── vpn/                   # VPN configuration templates
    ├── docker-compose.yml.j2  # Docker services configuration
    ├── sing-box.json.j2       # VPN server configuration
    ├── Caddyfile.j2           # Web server and TLS configuration
    └── cfgapp/                # Python configuration application
        ├── src/               # Application source code
        ├── tests/             # Test suite
        ├── examples/          # Template examples
        ├── pyproject.toml     # Python dependencies
        ├── Dockerfile         # Container configuration
        └── README.md          # CFG App documentation
```

## 🔧 CFG App Features

The CFG App (`vpn/cfgapp/`) provides:

- **Template Processing**: Process templates with RULE-SET and NETSET expansion
- **Authentication**: Built-in authentication system
- **Clash Support**: Full Clash YAML configuration processing
- **Proxy Configuration**: Dynamic proxy generation from JSON configuration
- **Subscription Support**: Multiple subscription tiers with query parameter selection
- **IP Aggregation**: Smart IP block aggregation and deduplication

### CFG App Configuration

Create a `.env` file in `vpn/cfgapp/` based on `vpn/cfgapp/env.example`:

```bash
# API Configuration
CONFIG_HOST=your-config-host.com
API_HOST=your-config-host.com

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

# Logging
LOG_LEVEL=INFO
```

## 🔒 Security Notes

- **TLS Certificates**: Automatically generated and managed by Caddy
- **Password Hashing**: Uses SHA256 with salt for secure password generation
- **Traffic Obfuscation**: Configurable obfuscation to bypass restrictions
- **Docker Isolation**: Services run in isolated containers
- **Port Configuration**: All ports are configurable via environment variables
- **Subscription Security**: Multi-tier access control with query parameter validation

## ⚙️ Environment Variables

| Variable | Description | Default | Required |
|----------|-------------|---------|----------|
| `SALT` | Secret salt for password hashing | - | Yes |
| `OBFS_PASSWORD` | Password for traffic obfuscation | - | Yes |
| `HTTP_PORT` | HTTP server port | 80 | No |
| `HTTPS_PORT` | HTTPS server port | 443 | No |
| `HYSTERIA2_PORT` | Hysteria2 VPN port | 47012 | No |
| `CONFIG_HOST` | Configuration hostname | - | Yes |

## 🐛 Troubleshooting

### Common Issues

1. **"SALT is not set" error**
   - Ensure `.env` file exists and contains `SALT` value
   - Run `cp env.example .env` and edit the file

2. **SSH connection issues**
   - Verify SSH key authentication is configured
   - Check server accessibility and firewall settings

3. **Docker installation fails**
   - Ensure target server has internet access
   - Check if Docker is already installed

4. **CFG App issues**
   - Ensure Poetry is installed: `curl -sSL https://install.python-poetry.org | python3 -`
   - Install dependencies: `cd vpn/cfgapp && poetry install`
   - Check environment variables in `vpn/cfgapp/.env`

### Logs and Debugging

- VPN server logs: `docker-compose logs sing-box`
- Web server logs: `docker-compose logs caddy`
- CFG App logs: Check application output during `make cfgapp-dev`
- Ansible verbose mode: Add `-v` flag to make commands

## 📝 License

[Add your license information here]

## 🤝 Contributing

[Add contribution guidelines here]
