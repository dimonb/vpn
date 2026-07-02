# Runbook — Deploy & everyday operations

Prereqs on the local machine: `ansible`, `make`, `jq`, `/usr/bin/ssh`. See [`AGENTS.md`](../AGENTS.md)
for the architecture and the profile table.

Throughout, pick the profile triple. Examples use **ebac**; for the **dimonb/personal** profile drop
the explicit args (they default to `.env` / `config.json` / `servers.cfg`).

```bash
# ebac
ENVF=.env.ebac ; CFG=config.ebac.json ; SRV=servers.ebac.cfg
# dimonb (defaults)
ENVF=.env      ; CFG=config.json      ; SRV=servers.cfg
```

## Deploy

```bash
# One host (safe — recommended for any change):
make deploy ENV_FILE=$ENVF CONFIG_FILE=$CFG SERVERS_FILE=$SRV TEST_ONLY=ru-1

# Whole inventory group (recreates containers on EVERY host in the group):
make deploy ENV_FILE=$ENVF CONFIG_FILE=$CFG SERVERS_FILE=$SRV
```

What it does: renders all `vpn/*.j2` templates onto the host(s), then
`docker compose build` + `up --pull always --force-recreate -d`. A successful run ends with
`failed=0`. The `error reading bcrypt version` traceback is a benign passlib warning on macOS.

> **Reminder:** deploy overwrites server-side configs from templates. Never fix a server by editing
> `/…/vpn/sing-box.json` in place — put the change in `config*.json` (data) or `vpn/*.j2` (logic).

## Validate BEFORE deploying (recommended for template/config edits)

1. **Render the config locally** for a specific host (no SSH; `-c local`):

```bash
cd <repo> ; set -a; source "$ENVF"; set +a
OUT=/tmp/rendered.sing-box.json
ansible ru-1 -i "$SRV" -c local \
  -e "salt=$SALT" -e "obfs_password=$OBFS_PASSWORD" -e "http_port=$HTTP_PORT" -e "https_port=$HTTPS_PORT" \
  -e "hysteria2_port=$HYSTERIA2_PORT" -e "hysteria2_v2_port=$HYSTERIA2_V2_PORT" -e "vless_port=$VLESS_PORT" \
  -e "reality_private_key=$REALITY_PRIVATE_KEY" -e "reality_public_key=$REALITY_PUBLIC_KEY" -e "reality_short_id=$REALITY_SHORT_ID" \
  -e "xray_mldsa65seed=$XRAY_MLDSA65SEED" -e "xray_privatekey=$XRAY_PRIVATEKEY" -e "xray_publickey=$XRAY_PUBLICKEY" -e "xray_verify=$XRAY_VERIFY" \
  -e "config_host=$CONFIG_HOST" -e "metrics_pwd=$METRICS_PWD" -e "config_file=$CFG" \
  -m template -a "src=vpn/sing-box.json.j2 dest=$OUT"
python3 -c "import json;json.load(open('$OUT'));print('JSON OK')"
```

2. **Run sing-box's own checker** on the target host (needs the cert mounted, so it doesn't false-fail):

```bash
/usr/bin/scp -q "$OUT" root@ru-1.outline.ebac.dev:/tmp/rendered.json
/usr/bin/ssh root@ru-1.outline.ebac.dev \
  'docker run --rm --entrypoint sing-box -v /tmp/rendered.json:/c.json \
     -v /home/ubuntu/vpn/cert:/etc/xray/certs itdoginfo/sing-box:v1.12.12 check -c /c.json; echo exit=$?'
```

3. **Check for drift** (make sure a deploy won't clobber a real manual change). Empty diff = safe.
   The only expected caddy.json diff is the two bcrypt metrics hashes (re-salted each render).

```bash
/usr/bin/ssh root@<host> 'cat /…/vpn/caddy.json' > /tmp/live.json
diff <(python3 -m json.tool /tmp/live.json) <(python3 -m json.tool /tmp/rendered.caddy.json)
```

## Verify AFTER deploying (drive the real path)

```bash
# 1) confirm outbounds/pools rendered as intended
/usr/bin/ssh root@<host> 'cd /…/vpn && python3 -c "import json,sys;c=json.load(open(\"sing-box.json\"));
[print(o[\"type\"],o.get(\"tag\"),o.get(\"server\",o.get(\"outbounds\"))) for o in c[\"outbounds\"]]"'

# 2) logs should be clean
/usr/bin/ssh root@<host> 'cd /…/vpn && docker compose logs sing-box --since 60s --no-color | grep -cE "EOF|failed"'

# 3) end-to-end: run a throwaway CLIENT against the host's own vless-in and check the exit IP.
#    Needs: uuid = sha256("system.$SALT")[:32] as 8-4-4-4-12 ; public_key = $REALITY_PUBLIC_KEY ;
#    short_id = $REALITY_SHORT_ID ; server_name/handshake = ok.ru ; connect to 127.0.0.1:$VLESS_PORT.
#    Start it with:  docker run -d --name cltest --network host --entrypoint sing-box \
#      -v /tmp/client.json:/c.json itdoginfo/sing-box:v1.12.12 run -c /c.json
#    Then:  curl --socks5-hostname 127.0.0.1:<port> https://ipinfo.io/json   → expect the EXIT node's IP.
```

(There is a ready-made version of the client-test snippet in `doc/RUNBOOK_dpi_failover.md`.)

## Add / remove a user

1. Edit the `users` array in `config*.json`.
2. Deploy (re-renders inbounds on every server with the new user).
3. Regenerate/print client credentials: `make passwords CONFIG_FILE=$CFG` (prints `user: sha256`).
   Client subscription links are produced by the `cfgapp` service (`BASE_URL`), or `make cfgapp-dev`
   to run it locally.

## Rollback

- Config lives in git-ignored `config*.json` + tracked `vpn/*.j2`. To roll back a template change:
  `git revert`/`git checkout` the template, then re-deploy.
- On-server backups: ad-hoc fixes leave `sing-box.json.bak.*` next to the config. A clean re-deploy
  always reproduces the template state regardless.

## Other Make targets

- `make install-docker …` — install Docker on new hosts.
- `make passwords CONFIG_FILE=…` — print per-user password hashes.
- `make cfgapp-dev …` — run the cfgapp locally against a config.
- `make ubuntu-update` / `ubuntu-upgrade` — OS maintenance playbooks.
