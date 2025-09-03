# VPN Deploy — Automated VPN Server Deployment

A complete solution for deploying VPN servers using Ansible, Docker, and Sing-Box with automatic TLS certificate management via Caddy. Includes a Python-based configuration application for proxy rule processing and subscription management.

> **⚠️ Disclaimer**: This configuration is provided for educational and personal use. Users are responsible for complying with local laws and regulations regarding internet usage and proxy services.

## 🚀 Features

- **Automated Deployment**: One-command deployment using Ansible
- **Docker-based**: Containerized VPN services for easy management
- **TLS Certificates**: Automatic HTTPS certificate generation with Caddy
- **User Management**: JSON-based user configuration with secure password generation
- **Subscription System**: Multi-tier subscription management with proxy configuration
- **CFG App**: Python application for proxy rule processing and NETSET expansion
- **Template Processing**: Support for Clash, Shadowrocket, and custom templates
- **QR Code Generation**: Easy client configuration sharing
- **Multi-Protocol Support**: Hysteria2, VMess, VLESS, and Reality protocols
- **IP Aggregation**: Smart IP block management and deduplication
- **Static File Serving**: Priority serving of static files (HTML, CSS, JS, images) before proxying to CFG App
- **JSON Configuration**: Caddy configured via JSON for better automation and version control

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
      "de_1_contabo": {"protocol": "hy2", "host": "de-1.your-domain.com"},
      "us_1_vultr": {"protocol": "vmess", "host": "us-1.your-domain.com"}
    },
    "premium": {
      "sg_1_linode": {"protocol": "vless", "host": "sg-1.your-domain.com"}
    }
  }
}
```

**Supported Protocols**:
- `hy2`: Hysteria2 protocol
- `vmess`: VMess protocol
- `vless`: VLESS protocol
- `reality`: Reality protocol (with automatic key generation)

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

### Generate Reality Keys (Optional)
```bash
make reality-keys
```

Generates Reality protocol keys for enhanced security and performance.

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

### System Maintenance
```bash
# Upgrade Ubuntu  stribution
make ubuntu-dist-upgrade

# Upgrade Ubuntu release
make ubuntu-release-upgrade
```

### Static File Management
```bash
# Add new static HTML page
echo '<h1>New Page</h1>' > vpn/static/new-page.html

# Add new CSS file
echo 'body { color: red; }' > vpn/static/css/custom.css

# Add new image (replace with actual image)
# cp your-image.png vpn/static/images/

# Restart Caddy to pick up changes
docker-compose restart proxy
```

## 📁 Project Structure

```
vpn/
├── README.md                    # This documentation
├── Makefile                     # Build automation
├── deploy_vpn.yml              # Ansible deployment playbook
├── install_docker.yml          # Docker installation playbook
├── ubuntu_dist_upgrade.yml     # Ubuntu distribution upgrade
├── ubuntu_release_upgrade.yml  # Ubuntu release upgrade
├── servers.cfg                 # Server inventory (create from example)
├── servers.cfg.example         # Server inventory template
├── config.json                 # User and subscription configuration
├── config.json.example         # Configuration template
├── .env                        # Environment secrets (create from example)
├── env.example                 # Environment template
├── generate_reality_keys.py    # Reality protocol key generator
├── generate_singbox_keys.py    # Sing-Box key generator
└── vpn/                        # VPN configuration templates
    ├── docker-compose.yml.j2   # Docker services configuration
    ├── sing-box.json.j2        # VPN server configuration
    ├── hysteria.yaml.j2        # Hysteria2 configuration
    ├── caddy.json.j2           # Web server and TLS configuration
    ├── caddy/                  # Caddy web server configuration
    │   └── Dockerfile         # Caddy container
    ├── static/                 # Static files (served with priority)
    │   ├── index.html          # Site under construction page
    │   ├── robots.txt          # Search engine directives (disallows all crawling)
    │   ├── test.html           # Test page for verification
    │   ├── css/
    │   │   └── style.css       # Main stylesheet
    │   ├── images/             # Image assets (create as needed)
    │   ├── js/                 # JavaScript files (create as needed)
    │   └── .gitkeep            # Git tracking file
    ├── json-exporter.yml       # Prometheus metrics exporter
    └── cfgapp/                 # Python configuration application
        ├── src/                # Application source code
        │   ├── auth.py         # Authentication system
        │   ├── clash_processor.py # Clash configuration processor
        │   ├── config.py       # Configuration management
        │   ├── main.py         # Main application entry point
        │   ├── processor.py    # Template processor
        │   ├── proxy_config.py # Proxy configuration
        │   └── utils.py        # Utility functions
        ├── tests/              # Test suite
        ├── examples/           # Template examples
        │   ├── clash_with_auth.tpl      # Clash with authentication
        │   ├── clash_with_proxies.tpl   # Clash with proxy rules
        │   └── shadowrocket.tpl         # Shadowrocket template
        ├── templates/          # HTML templates
        │   └── subscription.html        # Subscription page template
        ├── pyproject.toml      # Python dependencies
        ├── poetry.lock         # Locked dependencies
        ├── Dockerfile          # Container configuration
        ├── docker-compose.yml  # Local development setup
        ├── Makefile            # CFG App build automation
        └── README.md           # CFG App documentation
```

## 📁 Static File Serving

The `vpn/static/` directory contains static files that are served with priority by Caddy:

- **Priority Serving**: Static files are served first, before any requests are proxied to the CFG App
- **File Types**: HTML, CSS, JavaScript, images, and other static assets
- **Use Cases**: Landing pages, documentation, client downloads, and other static content
- **Performance**: Direct file serving without application processing overhead
- **Main Page**: The root path `/` now shows "Site is under construction" instead of the CFG App

### Static File Structure
```
vpn/static/
├── index.html          # Site under construction page
├── 404.html            # Custom error page for 404/500 errors
├── robots.txt          # Search engine directives (disallows all crawling)
├── test.html           # Test page for verification
├── css/
│   └── style.css       # Main stylesheet
├── images/             # Image assets (create as needed)
├── js/                 # JavaScript files (create as needed)
└── .gitkeep            # Ensures directory is tracked in git
```

### Adding Static Files
Simply place files in the `vpn/static/` directory and they will be automatically served. The file server will:
- Serve exact file matches (e.g., `/about.html` serves `static/about.html`)
- Serve directory indexes if `index.html` exists
- Fall back to CFG App for unmatched requests

**Note**: The `vpn/static/` directory is automatically deployed to all servers when you run `make deploy`. Any files you add to this directory will be available on all deployed servers.

## 🌐 Caddy Web Server Configuration

Caddy is configured via `caddy.json.j2` to serve content in the following priority order:

1. **Static Files** (`/static/` directory) - Highest priority
   - Direct file serving for HTML, CSS, JS, images
   - No application processing overhead
   - Ideal for landing pages and static content

2. **CFG App** (Python application) - Fallback
   - Handles dynamic requests and API calls
   - Processes templates and configurations
   - Manages subscriptions and user authentication

3. **Metrics Endpoints** - Special handling
   - `/node/metrics` - Node exporter metrics
   - `/hy2/metrics` - Hysteria2 metrics
   - Protected with basic authentication

### Request Flow
```
Request → Caddy → Static File Check → CFG App (if no static file found)
```

**Important**: Since `index.html` exists in the static directory, the root path `/` will always show "Site is under construction" and never reach the CFG App. To access the CFG App, use specific paths like `/cfg/`, `/subscription/`, etc.

### Static File Routing in caddy.json.j2
The JSON configuration explicitly defines static file handling:
- **Root path `/`**: Serves `index.html` from `/static` directory
- **Static assets**: `/css/*`, `/js/*`, `/images/*`, `/robots.txt`, `/test.html` are served directly
- **Fallback**: All other requests are proxied to the CFG App on port 8003

### Error Handling
- **Custom 404 Page**: Beautiful error page served from `/static/404.html` via CFG App
- **CFG App 404**: Returns proper 404 status codes when templates or paths are not found
- **Error Logging**: Comprehensive logging of all 404 and error responses
- **Fallback**: When CFG App returns 404, Caddy serves the custom error page

**Note**: The 404 page is served by CFG App when it cannot process a request, ensuring consistent error handling across all endpoints.

## 🔧 CFG App Features

The CFG App (`vpn/cfgapp/`) provides:

- **Template Processing**: Process templates with RULE-SET and NETSET expansion
- **Authentication**: Built-in authentication system with salt-based hashing
- **Clash Support**: Full Clash YAML configuration processing
- **Proxy Configuration**: Dynamic proxy generation from JSON configuration
- **Subscription Support**: Multiple subscription tiers with query parameter selection
- **IP Aggregation**: Smart IP block aggregation and deduplication
- **Shadowrocket Support**: iOS Shadowrocket configuration generation
- **Custom Templates**: Extensible template system for various clients

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

### CFG App Development

```bash
cd vpn/cfgapp

# Install dependencies
poetry install

# Run tests
poetry run pytest

# Run development server
poetry run python src/main.py

# Build Docker image
make build

# Run in Docker
make run
```

## 🔒 Security Features

- **TLS Certificates**: Automatically generated and managed by Caddy
- **Password Hashing**: Uses SHA256 with salt for secure password generation
- **Traffic Obfuscation**: Configurable obfuscation to bypass restrictions
- **Docker Isolation**: Services run in isolated containers
- **Port Configuration**: All ports are configurable via environment variables
- **Subscription Security**: Multi-tier access control with query parameter validation
- **Reality Protocol**: Enhanced security with automatic key generation
- **IP Filtering**: Configurable IP block management and filtering

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

5. **Reality protocol issues**
   - Run `make reality-keys` to generate new keys
   - Ensure keys are properly configured in templates

### Logs and Debugging

- VPN server logs: `docker-compose logs sing-box`
- Web server logs: `docker-compose logs caddy`
- CFG App logs: Check application output during `make cfgapp-dev`
- Ansible verbose mode: Add `-v` flag to make commands

### Testing

```bash
# Test Reality configuration
python test_reality.py

# Test Reality with real keys
python test_reality_real.py

# Test CFG App endpoints
cd vpn/cfgapp && poetry run pytest

# Test Docker builds
make test-docker-build

# Test static file serving (after deployment)
curl http://your-server-ip/
curl http://your-server-ip/css/style.css
curl http://your-server-ip/robots.txt
```

## 📊 Monitoring

- **Prometheus Metrics**: JSON exporter for monitoring VPN server metrics
- **Docker Health Checks**: Built-in health monitoring for all services
- **Log Aggregation**: Centralized logging through Docker Compose

## 🔄 Updates and Maintenance

### Regular Maintenance
```bash
# Update system packages
make ubuntu-dist-upgrade

# Update Docker images
docker-compose pull
docker-compose up -d

# Regenerate Reality keys (if needed)
make reality-keys
```

### Backup and Recovery
- Configuration files: `config.json`, `servers.cfg`, `.env`
- Docker volumes: VPN data and certificates
- User configurations: Generated client configs

## 📝 License

[Add your license information here]

## 🤝 Contributing

[Add contribution guidelines here]

## 📚 Additional Documentation

- [REALITY_SETUP.md](./REALITY_SETUP.md) - Reality protocol setup guide
- [vpn/cfgapp/README.md](./vpn/cfgapp/README.md) - CFG App detailed documentation
- [vpn/cfgapp/examples/](./vpn/cfgapp/examples/) - Template examples and usage
