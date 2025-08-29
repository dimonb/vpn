## VPN Deploy — Quick Start

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

4. Install Docker on hosts (one-time):
```bash
make install-docker
```

5. Deploy/Update:
```bash
make deploy
```

Notes:
- Users are read from `vpn/users.json`.
- TLS certs are auto-generated on the server to `~/vpn/cert`.
- Secrets are loaded from `.env`; `make deploy` fails if missing.
