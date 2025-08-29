## VPN Deploy — Quick Start

Requirements:
- Local: make, ansible, ssh, jq, sha256sum (coreutils) or shasum, qrencode (optional for `make cn`)
- Remote: Linux host with SSH access (Docker/Compose installed via `make install-docker`)

1. Clone repo and enter dir.

2. Copy env and set secrets:
```bash
cp env.example .env
# edit .env → set SALT and OBFS_PASSWORD
```

3. Copy inventory example and edit hosts:
```bash
cp servers.cfg.example servers.cfg
# edit servers.cfg
```

4. Copy users example and edit users:
```bash
cp vpn/users.json.example vpn/users.json
# edit vpn/users.json
```

5. Install Docker on hosts (one-time):
```bash
make install-docker
```

6. Deploy/Update:
```bash
make deploy
```

Notes:
- Users are read from `vpn/users.json`.
- TLS certs are auto-generated on the server to `~/vpn/cert`.
- Secrets are loaded from `.env`; `make deploy` fails if missing.

Passwords:
```bash
make passwords
# prints: <username>: <sha256(username.SALT)>
```
