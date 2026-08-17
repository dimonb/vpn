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

> **Select a profile by its `ENV_FILE` and let that carry the rest** — `.env.ebac` already sets
> `CONFIG_FILE`, `SERVERS_FILE`, `BASE_URL` and the ebac ports/secrets, so `make deploy ENV_FILE=.env.ebac`
> is the whole command ("остальное подхватится"). **Never hand-pass `CONFIG_FILE=`/`SERVERS_FILE=` from
> one row while leaving `ENV_FILE` on another row's value** — that ships one profile's secrets/ports onto
> the other profile's servers. See [Operating the deploy safely](#operating-the-deploy-safely-dont-shoot-your-own-foot).

> **`config*.json`, `.env*`, `servers*.cfg` are gitignored** (local only). Only the templates,
> playbook, Makefile, and `cfgapp` code are tracked. A fix that lives only in `config.json` is
> **not** in git — it lives on the operator's machine and is applied via deploy.

## How deploy works

```
make deploy ENV_FILE=.env.ebac [TEST_ONLY=<host>]     # ebac: .env.ebac carries CONFIG_FILE + SERVERS_FILE
make deploy                     [TEST_ONLY=<host>]     # personal: bare defaults (.env / config.json / servers.cfg)
```
1. `check-env` validates required vars are set in the ENV_FILE.
2. `ansible-playbook -i <SERVERS_FILE> deploy_vpn.yml -e "<vars from ENV_FILE>"`.
3. Per host: ensure `vpn/` dir + self-signed cert, rsync `cfgapp/` + `static/`, **render every
   `vpn/*.j2` template**, decide the docker daemon's egress (see
   [ghcr.io is unreachable from RU hosts](#ghcrio-is-unreachable-from-ru-hosts-images-are-mirrored-to-docker-hub)),
   then `docker compose build` + `up --pull always --force-recreate -d`.
- `TEST_ONLY=<host>` → `--limit <host>` (deploy to a single host). **Without it, the whole `vpn`
  inventory group is recreated.**
- **Consequence:** any hand-edit made directly on a server is **overwritten on the next deploy**.
  Persistent changes must go into the templates and/or `config*.json`.

### The deploy toolchain lives on the operator's laptop

`ansible-playbook` runs **locally**, and as of 2026-08-17 there was **no ansible installed at all** —
nothing in homebrew, pipx or `~/Library/Python` (most likely lost in the upgrade to Python 3.14).
`make deploy` cannot run until it's reinstalled, and the error is a bare `command not found: ansible`,
which is easy to misread as a PATH problem. What a working install needs:

- **`ansible-core` *plus* the `ansible.posix` collection.** `deploy_vpn.yml` calls
  `ansible.builtin.synchronize`, which actually lives in `ansible.posix`; with plain `ansible-core` the
  playbook fails already at `--syntax-check`:
  `couldn't resolve module/action 'ansible.builtin.synchronize'`.
- **`passlib`**, and **`bcrypt` pinned `<4.1`.** `vpn/caddy.json.j2` renders
  `metrics_pwd | password_hash('bcrypt')` and `METRICS_PWD` is longer than 72 bytes; bcrypt ≥ 4.1
  *raises* `password cannot be longer than 72 bytes` instead of truncating, so the deploy dies on the
  `caddy.json` item of the template loop.

**That bcrypt failure is nastier than it looks.** The template task is a `loop`, and `sing-box.json` +
`docker-compose.yml` are rendered onto the host **before** `caddy.json`, while `docker compose build` /
`up` come **after** it. So the run aborts leaving **new config files on disk with the old containers
still running** — not dangerous (rendered files are inert until the next `up`, see the safety window
below), but nothing has taken effect and a half-applied deploy is easy to mistake for a successful one.
Fix the pin and re-run.

- **Never `ps aux` an in-flight `ansible-playbook`** — its `-e` arguments carry `SALT`, the reality
  private keys and `METRICS_PWD` in plaintext in argv.

## Operating the deploy safely (don't shoot your own foot)

The Makefile has **two knobs that must agree**: the *secrets/ports* (from `ENV_FILE`) and the
*config + inventory* (`CONFIG_FILE` + `SERVERS_FILE`). Each profile above is a matched set. `make`
does **not** warn if you cross them, and the classic self-inflicted wound is deploying **one
profile's secrets onto another profile's servers.**

**Golden rule — the three knobs must come from the same profile row.** Two safe forms:
- pass only `ENV_FILE=.env.ebac` (it already supplies `CONFIG_FILE`+`SERVERS_FILE`) — simplest for ebac; or
- set all three explicitly as one matched triple (the `ENVF/CFG/SRV` vars in [`doc/RUNBOOK_deploy.md`](doc/RUNBOOK_deploy.md)).

**The footgun is specifying *some but not all*** — e.g. `make deploy CONFIG_FILE=config.ebac.json
SERVERS_FILE=servers.ebac.cfg` **without** `ENV_FILE`. That silently pairs the ebac servers with the
*default* `.env`'s salt/ports (the personal profile). If you're typing `CONFIG_FILE=`/`SERVERS_FILE=`,
you **must** also set the matching `ENV_FILE=` — or just drop them and use `ENV_FILE=` alone.

**Why a mismatch is destructive** (all silent — no error, the deploy "succeeds"):
- **Wrong `SALT`** → every credential is `sha256("<user>.<SALT>")`, so all hy2 passwords / vless UUIDs
  change at once. Existing client subscriptions stop authenticating ⇒ **fleet-wide outage** until every
  user re-fetches. This is the worst one.
- **Wrong `HYSTERIA2_PORT` / `HYSTERIA2_V2_PORT`** → sing-box binds ports the clients don't dial ⇒ hy2 dead.
- **Wrong `OBFS_PASSWORD`** → salamander obfs mismatch ⇒ connections rejected.

**Pre-flight, every time:**
1. **Read the first banner line** the deploy prints — it echoes the ports:
   `Using ports - … Hysteria2: 47024, Hysteria2-v2: 47031` ⇒ **ebac**; `47012 / 47013` ⇒ **personal**.
   Wrong number for the fleet you're targeting = wrong `ENV_FILE` ⇒ **abort immediately.**
2. For a risky or first-of-its-kind change, scope to one host with `TEST_ONLY=<host>` before the fleet.
3. Run it in the background and watch to the end — `up --force-recreate` restarts every container, i.e. a
   brief connectivity blip for all users on each host.

**There is a safety window — use it.** The playbook runs strictly in this order: rsync code → **render
all `vpn/*.j2` templates to disk** → `docker compose build` → `docker compose up --force-recreate`.
Only that last task swaps the *running* services. Therefore:
- Catch a mistake **before** the `Build docker-compose apps` / `Run Docker Compose` tasks → **stop the run**
  (TaskStop / Ctrl-C). The mis-rendered files sit on disk but are **inert**; the live containers keep their
  previous good config. **No user impact.** (Files rendered onto hosts are only picked up on the *next*
  `up`.)
- **Recovery is just: re-run with the correct `ENV_FILE`.** It re-renders every template (overwriting the
  bad files) and force-recreates the containers correctly. Nothing else to clean up on the hosts.
- If the recreate step already ran with the wrong profile, the breakage is live — recover the same way,
  immediately: re-deploy the correct profile.

**Two more foot-guns:**
- `config*.json` / `.env*` / `servers*.cfg` are **gitignored** — a fix living only there is not in git,
  it's on the operator's laptop. Back up the salts; losing them logs everyone out.
- Never edit configs directly on a server — the next deploy wipes them. Change the template / `config*.json`.

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

## cfgapp's own egress on relays (origin fetches go through the tunnel)

`cfgapp` is not just a config renderer — for every request it fetches the origin
(`CONFIG_HOST`, e.g. `shadowrocket.ebac.dev`) twice: the bare path, then `<path>.tpl` when the
first is a 404. The origin is a GitHub Pages site, and **GH Pages' anycast IPs are partially
blocked from RU networks** (2026-08-17: only `185.199.110.153` of the four answered from both
ru-0/Yandex and ru-2/kvmka; the other three had their SYN dropped). DNS round-robin then makes
each fetch a coin flip and two fetches per request compound it — `~6%` success, which reads as a
flapping host, not a blocked origin.

So on relays cfgapp does **not** go out directly:

- `sing-box.json.j2` adds a `mixed` inbound `cfgapp-in` on `172.29.77.1:1080`, password-protected
  with `sha256("cfgapp-proxy." + SALT)`, plus a `route.rules` entry pinning that inbound to `auto`.
- `docker-compose.yml.j2` creates a dedicated bridge `vpn-tunnel` with a **pinned** subnet
  (`172.29.77.0/29`) so the gateway address sing-box binds is deterministic, attaches only
  `cfgapp` to it, and sets `HTTP_PROXY`/`HTTPS_PROXY` to that inbound (httpx honours them via
  `trust_env`). `NO_PROXY=localhost,127.0.0.1`.
- Both are gated on `forward_group` — leaf/exit hosts render exactly as before, no inbound, no
  network, no proxy env.

This also fixes the rule-set/netset fetches the template processor makes (`raw.githubusercontent.com`
is blocked from RU too). Verify with `docker logs vpn-sing-box-1 | grep cfgapp-in` — you should see
`inbound/mixed[cfgapp-in] → outbound/hysteria2[<exit>]`.

`forward_request` in `vpn/cfgapp/src/main.py` uses a **3 s** timeout with **3 attempts** (each a
fresh connection, so a direct-route retry also re-resolves and lands on a different address).
Don't raise it back to a single 30 s attempt: a stalled origin then holds the request past the
monitoring timeout and the whole host looks down.

## ghcr.io is unreachable from RU hosts (images are mirrored to Docker Hub)

**ghcr.io is blocked from Russian networks.** Only the `xray` image came from there (the rest are
Docker Hub, which is reachable), and going direct the deploy's last task —
`docker compose up --pull always …` — cannot succeed on a RU host:

```
Error response from daemon: Head "https://ghcr.io/v2/xtls/xray-core/manifests/26.2.6": EOF
```

(also seen as `… TLS handshake timeout`.) 2026-08-17: it hit `ru-2.kvmki.v.dimonb.com` on every
deploy; `ru-0.yandex.v.dimonb.com` only got through because it had the manifest cached.

**Fix: the image is mirrored, so nothing the deploy pulls lives on a blocked registry.**
`vpn/docker-compose.yml.j2` uses `dimonb/xray-core:26.2.6` — a copy of `ghcr.io/xtls/xray-core`
with the *same digest* (`sha256:c6daec52…`, the full 9-platform index). `make mirror-images` re-runs
the copy from the `MIRROR_IMAGES` list in the Makefile; it uses `crane` (registry→registry, no
docker daemon) and prints both digests so you can see they match. **After bumping the xray version
in `docker-compose.yml.j2`, bump it in `MIRROR_IMAGES` and run `make mirror-images` — otherwise RU
hosts pull a tag that does not exist yet.**

**Belt and braces: when a relay's tunnel is up, dockerd pulls through it anyway.** `deploy_vpn.yml`
renders `vpn/docker-http-proxy.conf.j2` → `/etc/systemd/system/docker.service.d/http-proxy.conf`
(mode `0600`, root — it carries the proxy password), setting `HTTP_PROXY`/`HTTPS_PROXY` to
`http://cfgapp:<sha256("cfgapp-proxy."+SALT)>@172.29.77.1:1080`, i.e. the `mixed` inbound
`cfgapp-in` that a `route.rules` entry pins to `auto` (hysteria2 → EU exit). `NO_PROXY` keeps
loopback, this host's own names/IP and all RFC1918 + link-local direct (docker bridges incl.
`vpn-tunnel`, the LAN, cloud metadata `169.254.169.254`). That keeps a path open if Docker Hub ever
joins the blocklist, without making the tunnel a prerequisite for deploying.

- **Relay-gated exactly like the templates** (`proxy.<ansible_host>.features.forward-nonru` present
  *and* its subs group exists — the same `lookup('file', config_file) | from_json` dance as
  `docker-compose.yml.j2`). Leaf/exit hosts have working direct egress: the drop-in is **removed**
  there, never installed.
- **And port-gated.** The play probes `172.29.77.1:1080` (`wait_for`, 5 s, `ignore_errors`) and only
  installs the drop-in if something answers; otherwise it *removes* it, so pulls fall back to direct
  egress instead of dying on a dead proxy. This is what makes a **first** deploy to a new RU relay
  possible at all: the `vpn-tunnel` bridge does not exist until the first `docker compose up`
  creates it, so the probe on a fresh host is guaranteed to fail. Use `ignore_errors`, **not**
  `failed_when: false` — the latter forces `failed=False` and leaves nothing to branch on.
- dockerd reads its proxy from the environment **at start**, so the play does `daemon-reload` +
  `systemctl restart docker` — **only when the drop-in actually changed** (registered result, not a
  blind restart). That restart bounces *every* container on the box, VPN and non-VPN alike (on ru-0
  that's `freeswitch`, `shadowbox`, `watchtower` too), which is why it must stay change-gated. The
  play then `wait_for`s `172.29.77.1:1080` (180 s) so the tunnel it just pointed dockerd at is back
  after the bounce — and **if it does not come back, the drop-in is removed and docker restarted
  again**, i.e. the deploy backs itself out to direct pulls rather than failing.
- **Ordering matters and is deliberate**: the drop-in tasks sit *after* the template render loop and
  *before* `docker compose build` / `up --pull always`, so the proxy is in effect for the pull.
- When the pull does cross the tunnel it crosses a DPI-ridden path, and compose aborts the *whole*
  pull on the first error — e.g. `remote error: … lookup auth.docker.io: unexpected EOF`, the exit's
  DNS hiccuping (seen once on ru-2, right after the docker restart; the very same pull succeeded on
  retry). So `Run Docker Compose` has `until rc == 0` / `retries: 2` / `delay: 20`.
- Verify: `systemctl show docker --property=Environment` shows the proxy (or doesn't, when the
  tunnel was down), and `docker logs vpn-sing-box-1 | grep -E 'registry|docker\.io'` shows
  `inbound/mixed[cfgapp-in] … outbound/hysteria2[<exit>]` — i.e. the pull left via the tunnel.

**Consequences worth remembering:**
- **Never run `docker system prune` / `docker image prune -a` on a RU host.** Less lethal now that
  the images sit on Docker Hub, but the stack needs them to start at all and RU egress is fragile.
- A new upstream image added to the compose file must be checked against RU reachability; if it
  isn't on Docker Hub, mirror it (add it to `MIRROR_IMAGES`) rather than relying on the tunnel.

Same family of problem as GH Pages / `raw.githubusercontent.com` being partly blocked from RU — see
[cfgapp's own egress on relays](#cfgapps-own-egress-on-relays-origin-fetches-go-through-the-tunnel).

## RULE-SET / NETSET lists are cached on disk (and served stale on failure)

**2026-08-17, second incident of the day.** `raw.githubusercontent.com` started answering `429 Too
Many Requests` — globally, not to us specifically (reproduced from the laptop and from ie-0, on an
unrelated repo; `github.com` itself was fine, `x-served-by: cache-…-DUB`, i.e. Fastly). Every list
fetch failed, and since the strict contract turns a failed list into a hard error, both RU relays
served `502` for `/contabo.conf` and Gatus paged.

The contract was right; the architecture around it was not. cfgapp re-fetched **every** list on
**every** request — 5 URLs (`lord-alfred/ipranges` amazon+apple v4/v6, `HybridNetworks/whatsapp-cidr`)
× ~183 requests/hour on ru-0 alone ≈ 900 GitHub hits/hour per host, for files that change once a day.
Both relays exit through the same ie-0 address, so upstream saw ~1800/hour from one IP.

**Fix: `src/listcache.py`, a content-addressed on-disk cache** (sha256 of the URL → `<digest>.body`),
wired into `TemplateProcessor.fetch_list_text()`:

| state of the cached copy | behaviour |
|---|---|
| younger than `list_cache_fresh_seconds` (24 h) | serve it, **no network request at all** |
| older | re-fetch, store the new body |
| re-fetch failed, copy < `list_cache_max_age_seconds` (30 d) | **serve the stale copy**, log a warning |
| nothing usable on disk | raise `ListFetchError` → 502/504, as before |

- **The file's mtime is the timestamp.** No sidecar metadata to drift out of sync, and `ls -l` in the
  volume tells you the whole story.
- **Lives in a named volume** `vpn-cfgapp-cache` → `/cache`, so it survives the deploy's
  `--force-recreate`. It must be a *named* volume, not a bind mount: cfgapp runs as the unprivileged
  `app` user (uid 1000) and could not write a host directory docker created as root — the volume
  inherits ownership from `/cache` in the image instead (`Dockerfile`: `mkdir -p /cache/lists &&
  chown -R app:app /cache`).
- **Every filesystem error is swallowed and logged.** A broken cache degrades to "fetch every time",
  never to a failed request. Writes go through a temp file + `os.replace`, so a crash cannot leave a
  half-written list that then looks valid for a month.
- **Single-flight**: a module-level lock per cache key, so a TTL expiry sends *one* request upstream
  instead of one per concurrent client. Waiters re-read the cache after the lock and get what the
  leader wrote.
- **Failure backoff** (`LIST_FAILURE_BACKOFF`, 60 s): after a failure, requests holding a stale copy
  skip the network entirely for a minute. Without it every request would pay
  `LIST_ATTEMPTS × LIST_TIMEOUT` = 45 s per broken list before falling back — serialized behind the
  single-flight lock, which would be far worse than the outage itself. Gatus's timeout is 48 s.
- The same-host branch of `smart_fetch` (RULE-SETs proxied via `API_HOST`, our own origin) is
  **deliberately uncached** — the response varies with the caller's headers and a config edit must
  not take a day to appear. `API_HOST` is unset in production, so that branch is dormant anyway.
- Tunables, all env-overridable: `LIST_CACHE_DIR`, `LIST_CACHE_FRESH_SECONDS`,
  `LIST_CACHE_MAX_AGE_SECONDS`. Inspect with
  `docker run --rm -v vpn-cfgapp-cache:/c alpine ls -l /c/lists`.
- Tests isolate the cache per-test via `tests/conftest.py` (autouse, points `list_cache_dir` at
  `tmp_path`). **Without it a body cached by one test satisfies the next test's fetch**, the mocked
  client goes uncalled, and assertions fail for no visible reason — remember this when adding tests.

The 502-instead-of-truncation contract itself is unchanged; see
[cfgapp's own egress on relays](#cfgapps-own-egress-on-relays-origin-fetches-go-through-the-tunnel).

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
- The `error reading bcrypt version` traceback during `make deploy` (passlib/bcrypt on macOS) is **non-fatal** — the caddy template still renders. A *fatal* `password cannot be longer than 72 bytes` from the same area means bcrypt ≥ 4.1 — see [The deploy toolchain lives on the operator's laptop](#the-deploy-toolchain-lives-on-the-operators-laptop).
- **Never `docker system prune` / `docker image prune -a` on a RU host** — RU egress to registries is fragile and the stack cannot start without its images: [ghcr.io is unreachable from RU hosts](#ghcrio-is-unreachable-from-ru-hosts-images-are-mirrored-to-docker-hub).
- **Bumping the xray version means two edits**: the tag in `vpn/docker-compose.yml.j2` *and* `MIRROR_IMAGES` in the Makefile, then `make mirror-images` — RU hosts pull the mirror, not ghcr.io.

## Common tasks → runbooks

- **Deploy / validate / render locally / add-remove user** → [`doc/RUNBOOK_deploy.md`](doc/RUNBOOK_deploy.md)
- **VPN "stopped working" from Russia (DPI blocking) → Hysteria2 failover** → [`doc/RUNBOOK_dpi_failover.md`](doc/RUNBOOK_dpi_failover.md)
- Reality key setup → [`doc/REALITY_SETUP.md`](doc/REALITY_SETUP.md)
- cfgapp / NetworkCompactor → [`doc/README_COMPACTOR.md`](doc/README_COMPACTOR.md), [`doc/INTEGRATION_SUMMARY.md`](doc/INTEGRATION_SUMMARY.md)
