# AGENTS.md — orientation for this repo

VPN deployment stack: **Ansible** renders Jinja templates onto remote hosts and runs a
**docker compose** bundle (sing-box, xray, caddy, hysteria, a Python `cfgapp`, exporters).
This file explains *what is where and how it fits together*. For step-by-step operations see
the runbooks in [`doc/`](doc/).

> ⚠️ The real layout is **flat** — `deploy_vpn.yml` at the root + templates under `vpn/`.
> (Older notes mention `playbooks/`/`roles/` — those do not exist.)

## Repo layout

| Path | What it is |
|---|---|
| `Makefile` | Entry point. `make deploy`, `make install-docker`, `make passwords`, `make cfgapp-dev`, `make render-template-test`. |
| `deploy_vpn.yml` | The **only** deploy playbook. Renders templates → `docker compose build` → `up --force-recreate`. |
| `vpn/*.j2` | Server config **templates** (Jinja2), rendered per host: `sing-box.json.j2`, `xray.json.j2`, `caddy.json.j2`, `docker-compose.yml.j2`, `hysteria.yaml.j2`. |
| `vpn/cfgapp/` | Python (FastAPI) service that builds **client subscription** configs (Clash/Shadowrocket/etc.) and does NETSET/IP compaction. Deployed as the `cfgapp` container. Has its own `.venv`, tests. |
| `vpn/static/` | Decoy website + error pages served by caddy. |
| `config*.json` | **Data**: user list + subscription groups (`subs`) + which hosts are relays (`proxy`). |
| `.env*` | **Secrets/ports**: `SALT`, `OBFS_PASSWORD`, `METRICS_PWD`, reality/xray keys, port numbers. |
| `servers*.cfg` | Ansible inventory (group `vpn`). |
| `doc/` | Docs + runbooks (see below). |

### Deploy profiles (pick one triple)

Everything is parameterised, so there are multiple independent deployments sharing the same
templates. Pick a matching `ENV_FILE` / `CONFIG_FILE` / `SERVERS_FILE`:

| Profile | ENV_FILE | CONFIG_FILE | SERVERS_FILE | ansible_user | HYSTERIA2_PORT |
|---|---|---|---|---|---|
| ebac (corp) | `.env.ebac` | `config.ebac.json` | `servers.ebac.cfg` | `ubuntu` (+sudo) | 47024 |
| dimonb (personal) | `.env` (default) | `config.json` | `servers.cfg` | `root` | 47012 |

> **`config*.json`, `.env*`, `servers*.cfg` are gitignored** (local only). Only the templates,
> playbook, Makefile, and `cfgapp` code are tracked. A fix that lives only in `config.json` is
> **not** in git — it lives on the operator's machine and is applied via deploy.

## How deploy works

```
make deploy ENV_FILE=.env.ebac CONFIG_FILE=config.ebac.json SERVERS_FILE=servers.ebac.cfg [TEST_ONLY=<host>]
```
1. `check-env` validates required vars are set in the ENV_FILE.
2. `ansible-playbook -i <SERVERS_FILE> deploy_vpn.yml -e "<vars from ENV_FILE>"`.
3. Per host: ensure `vpn/` dir + self-signed cert, rsync `cfgapp/` + `static/`, **render every
   `vpn/*.j2` template**, then `docker compose build` + `up --pull always --force-recreate -d`.
- `TEST_ONLY=<host>` → `--limit <host>` (deploy to a single host). **Without it, the whole `vpn`
  inventory group is recreated.**
- **Consequence:** any hand-edit made directly on a server is **overwritten on the next deploy**.
  Persistent changes must go into the templates and/or `config*.json`.

## How a host's role is decided (relay vs leaf)

The same `sing-box.json.j2` produces different configs based on `config.proxy[<ansible_host>]`:

- **Leaf / exit node** (no `proxy` entry): outbounds = just `direct-out`; it only serves its own
  inbounds (vless-reality on `VLESS_PORT`, hysteria2 on `HYSTERIA2_PORT`) behind caddy.
- **Relay / entry node** (`proxy.<host>.features.forward-nonru = "<subs-group>"`): the template
  builds a `urltest` outbound named `auto` from every member of that subs group, renders one
  outbound per member, and sets `route.final = auto`. `forward-il` → a second pool `auto-il`.
  Per-member `protocol` decides the outbound type:
  - `hy2` / `hy2-v2` → **hysteria2** outbound (`server:HYSTERIA2_PORT`, salamander obfs, alpn h3).
  - `vless-v2` → **vless-reality** outbound (`server:HTTPS_PORT`, utls chrome, reality).

So "change a relay's upstream transport" = **edit `protocol` in `config*.json`** (no template change).

## DNS resolution on relays (aligned with routing)

Relays resolve DNS the same way they route traffic, so direct-routed names keep working when the
tunnel is down and the DPI can't poison lookups (`vpn/sing-box.json.j2`, all relay-gated on
`forward_group`):

- **tunnel-routed traffic → resolve through the tunnel.** `route.default_domain_resolver` = `quad9-doh`
  (a DoH server with `detour: "auto"`). Foreign domains resolve unpoisoned at the exit → correct IPs →
  route to the tunnel. (Plaintext 9.9.9.9 from Russia is DPI-disrupted; without this, foreign domains
  got mis-resolved and misrouted to `direct-out`, failing with `unexpected EOF`.)
- **direct-routed traffic → resolve locally.** `direct-out` and the `domain-ru` DNS rule use `local-dns`
  (`type: local`, the box's system resolver) — RU/direct traffic resolves from the RU perspective and
  works even if the tunnel is down.
- **exit server addresses → resolve directly.** Each exit outbound sets `domain_resolver: "bootstrap"`
  (udp 9.9.9.9). This prevents the "resolve the tunnel through the tunnel" deadlock — exit domains
  always resolve without the tunnel, so it can always come up.

sing-box has **no on-failure DNS failover**; this destination-split is the robust equivalent.
`unexpected EOF` for `direct-out` lookups in the first ~70 s after a restart is a benign cold-start
artifact (remote geoip/geosite rule-sets still downloading).

## Per-site routing (send a domain direct / to a specific exit)

Single source of truth is the inline `domain-ru` rule_set — both the DNS rule
(`{"rule_set":"domain-ru","server":"local-dns"}`) and the route rule (`domain-ru → direct-out`) use it.

- **RU site on a reachable RU IP** (e.g. `fanfics.me`): add it to `domain-ru` → resolves local + routes
  direct (fast; avoids the RU→EU→RU detour).
- **Censored-in-RU + Cloudflare-fronted site** (e.g. `ficbook.net`): direct is impossible (DPI drops the
  TLS ClientHello by SNI) so it must go through a tunnel; Cloudflare then serves a JS challenge a real
  browser passes but a datacenter exit IP may get challenge-looped. Pinned to a specific exit via a
  `route.rules` entry gated on that exit being present (`'am-1.outline.ebac.dev' in fwd_hosts`). A
  residential/mobile RU-region exit would avoid the challenge; we don't have one.

## Credentials & keys (all derived, keep consistent per profile)

- **Per-user secret** = `sha256("<user>.<SALT>")`.
  - hysteria2 **password** = the full hex digest.
  - vless **uuid** = first 32 hex chars formatted `8-4-4-4-12`.
  - The `system` user is what relays use to authenticate to upstreams.
- **Reality**: `REALITY_PRIVATE_KEY`/`REALITY_PUBLIC_KEY` (x25519; public is derivable from private
  via `xray x25519 -i <priv>` or an X25519 computation), `REALITY_SHORT_ID`. Client `public_key`
  must match the server's `private_key` — mismatch ⇒ handshake `EOF`. See `generate_reality_keys.py`.
- **obfs**: salamander password = `OBFS_PASSWORD`. **metrics**: basic-auth `METRICS_PWD` (bcrypt in
  caddy, re-salted every render — the two changed hashes in a caddy.json diff are benign).

## Traffic path

```
client ──443──▶ caddy (layer4, routes by TLS SNI)
                 ├─ SNI ok.ru            → 127.0.0.1:VLESS_PORT   (sing-box vless-in, reality)
                 ├─ SNI www.icloud.com   → 127.0.0.1:28443        (xray reality)
                 └─ default              → 127.0.0.1:4443         (decoy site / cfgapp)
client ──UDP HYSTERIA2_PORT──▶ sing-box hysteria2-in (salamander obfs)

on a RELAY: inbound ─▶ route rules ─▶ auto(urltest) ─▶ hy2/vless outbound ─▶ EXIT node ─▶ internet
            (geoip-ru / domain-ru / private IPs ─▶ direct-out)
            (DNS on relays is split like routing: tunnel-routed → DoH-via-tunnel, direct-routed →
             local resolver, exit addresses → direct 9.9.9.9 — see "DNS resolution on relays")
```

## Gotchas

- **`ssh` is aliased to kitty's ssh-kitten** in this environment → use **`/usr/bin/ssh`** / `/usr/bin/scp` for non-interactive commands.
- **ebac servers**: root SSH key is on `ru-1`; **`am-1` (Yerevan exit) is root-only** — connect `root@am-1` with `-o IdentitiesOnly=yes -i ~/.ssh/id_rsa`, and its dir is `/root/vpn` (inventory line carries the per-host `ansible_user=root` override). For the rest connect as **`ubuntu@` + `sudo`**; the `vpn/` dir is root-owned (`drwx------`), so `sudo bash -c 'cd /home/ubuntu/vpn && …'`.
- **`ru-2.kvmki.v.dimonb.com` also runs FreeSWITCH**; its VPN dir is `/root/vpn`. Deploy only touches the docker-compose stack there — FreeSWITCH is separate.
- **Mainline sing-box (`itdoginfo/sing-box:v1.12.12`) has no `tls_fragment`** — that field is rejected.
- Validate a rendered config with sing-box's own checker (needs the cert mounted):
  `docker run --rm --entrypoint sing-box -v /path/sing-box.json:/c.json -v /path/cert:/etc/xray/certs itdoginfo/sing-box:v1.12.12 check -c /c.json`
- The `error reading bcrypt version` traceback during `make deploy` (passlib/bcrypt on macOS) is **non-fatal** — the caddy template still renders.

## Common tasks → runbooks

- **Deploy / validate / render locally / add-remove user** → [`doc/RUNBOOK_deploy.md`](doc/RUNBOOK_deploy.md)
- **VPN "stopped working" from Russia (DPI blocking) → Hysteria2 failover** → [`doc/RUNBOOK_dpi_failover.md`](doc/RUNBOOK_dpi_failover.md)
- Reality key setup → [`doc/REALITY_SETUP.md`](doc/REALITY_SETUP.md)
- cfgapp / NetworkCompactor → [`doc/README_COMPACTOR.md`](doc/README_COMPACTOR.md), [`doc/INTEGRATION_SUMMARY.md`](doc/INTEGRATION_SUMMARY.md)
