# VPN Deploy — Automated VPN Server Deployment

A complete solution for deploying VPN servers using Ansible, Docker, and Sing-Box with automatic TLS certificate management via Caddy.

## 🚀 Features

- **Automated Deployment**: One-command deployment using Ansible
- **Docker-based**: Containerized VPN services for easy management
- **TLS Certificates**: Automatic HTTPS certificate generation with Caddy
- **User Management**: Simple JSON-based user configuration
- **Password Generation**: Secure password hashing with salt
- **QR Code Generation**: Easy client configuration sharing

## 📋 Requirements

### Local Machine
- `make` - Build automation tool
- `ansible` - Configuration management
- `ssh` - Secure shell client
- `jq` - JSON processor
- `sha256sum` (coreutils) or `shasum` - Hash utility
- `qrencode` - QR code generation (optional, for `make cn`)

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
```

**Important**: 
- `SALT` is used for password hashing - keep it secret and consistent
- `OBFS_PASSWORD` is used for traffic obfuscation - use a strong password
- `HTTP_PORT` is the port for HTTP traffic (default: 80)
- `HTTPS_PORT` is the port for HTTPS traffic (default: 443)
- `HYSTERIA2_PORT` is the port for Hysteria2 VPN protocol (default: 47012)

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

**Tips**:
- Use hostname or `1.2.3.4.sslip.io` for valid HTTPS connections
- Ensure SSH access is configured (key-based authentication recommended)

### 4. Configure Users
Copy the users template:
```bash
cp vpn/users.json.example vpn/users.json
```

Edit `vpn/users.json` with your user list:
```json
[
  "user1",
  "user2",
  "user3"
]
```

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
├── .env                   # Environment secrets (create from example)
├── env.example            # Environment template
└── vpn/                   # VPN configuration templates
    ├── docker-compose.yml.j2  # Docker services configuration
    ├── sing-box.json.j2       # VPN server configuration
    ├── Caddyfile.j2           # Web server and TLS configuration
    ├── users.json             # User list (create from example)
    └── users.json.example     # User list template
```

## 🔒 Security Notes

- **TLS Certificates**: Automatically generated and managed by Caddy
- **Password Hashing**: Uses SHA256 with salt for secure password generation
- **Traffic Obfuscation**: Configurable obfuscation to bypass restrictions
- **Docker Isolation**: Services run in isolated containers
- **Port Configuration**: All ports are configurable via environment variables

## ⚙️ Environment Variables

| Variable | Description | Default | Required |
|----------|-------------|---------|----------|
| `SALT` | Secret salt for password hashing | - | Yes |
| `OBFS_PASSWORD` | Password for traffic obfuscation | - | Yes |
| `HTTP_PORT` | HTTP server port | 80 | No |
| `HTTPS_PORT` | HTTPS server port | 443 | No |
| `HYSTERIA2_PORT` | Hysteria2 VPN port | 47012 | No |

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

### Logs and Debugging

- VPN server logs: `docker-compose logs sing-box`
- Web server logs: `docker-compose logs caddy`
- Ansible verbose mode: Add `-v` flag to make commands

## 📝 License

[Add your license information here]

## 🤝 Contributing

[Add contribution guidelines here]
