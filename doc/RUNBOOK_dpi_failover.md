# Runbook — VPN dead from Russia (DPI / TSPU) → Hysteria2 failover

**Symptom:** clients on a Russian **relay** node (`ru-*`) stop reaching the internet. Relay logs
show floods of `outbound/urltest[auto]: EOF` and `dns: lookup failed … unexpected EOF`.

## TL;DR of the failure mode

Russian TSPU/DPI **silently drops the TLS ClientHello** on the relay→exit (RU→EU) path:

- TCP handshake (SYN/SYN-ACK/ACK) completes and **plain (non-TLS) bytes pass**, but the first
  packet carrying a **TLS ClientHello never arrives** at the exit node. Reality's camouflage does
  not help — the packet is dropped before any content check matters.
- It hits **every** vless-reality upstream on `:443` (and direct xray/DoH too), regardless of port.
- **Not the cause:** reality keys, `short_id`, caddy, the exit nodes (all verified healthy from the
  exit's own localhost). Do **not** regenerate keys.
- Byte-level TCP fragmentation did **not** evade it, and mainline sing-box has no `tls_fragment`.

**Fix that works: move the relay→exit hop to Hysteria2 (UDP/QUIC), which the DPI lets through.**
DoH-to-Quad9 (also TLS) is disrupted the same way, so on relays DNS is sent through the tunnel.

## 1. Confirm the diagnosis

Run from the **relay** (the RU box). `$UP` = an upstream/exit host (e.g. `fr-2.example.org`).

```bash
# a) vless path dead? TCP connects but TLS handshake never completes:
timeout 8 openssl s_client -connect $UP:443 -servername www.icloud.com </dev/null 2>&1 | grep -q subject= \
  && echo "vless OK" || echo "vless BLOCKED (no handshake)"

# b) EOF flood in relay logs:
docker compose logs sing-box --since 10m --no-color | grep -cE "urltest.*EOF|dns: lookup failed"

# c) (definitive) tcpdump ON THE EXIT node while triggering a handshake from the relay:
#    exit: sudo tcpdump -ni any "host <relay-ip> and tcp port 443" -c 40 -tt
#    relay: the openssl from (a)
#    → you see S / S. / . then NOTHING (the ClientHello data packet never lands). Plain bytes DO land.
```

Also confirm the exit node itself is healthy (rules out an exit problem) — from the **exit's** localhost:
```bash
openssl s_client -connect 127.0.0.1:28443 -servername www.icloud.com </dev/null 2>&1 | grep subject=  # xray reality → real Apple cert
openssl s_client -connect 127.0.0.1:8443  -servername ok.ru        </dev/null 2>&1 | grep subject=  # sing-box reality
```

## 2. Verify Hysteria2 survives BEFORE changing config

From the **relay**, spin up a throwaway sing-box client (socks → hysteria2 → exit) and check egress.
Creds are profile-derived: `password = sha256("system.$SALT")`, obfs = `$OBFS_PASSWORD`, port =
`$HYSTERIA2_PORT` (work 47024, personal 47012). Use the exit's IP.

```bash
IMG=$(docker inspect vpn-sing-box-1 --format '{{.Config.Image}}')
PW=$(python3 -c 'import hashlib,os;print(hashlib.sha256(("system."+os.environ["SALT"]).encode()).hexdigest())')
IP=$(getent hosts "$UP" | awk '{print $1}' | head -1)
cat >/tmp/hy.json <<EOF
{"log":{"level":"error"},
 "inbounds":[{"type":"socks","tag":"s","listen":"127.0.0.1","listen_port":11090}],
 "outbounds":[{"type":"hysteria2","tag":"hy","server":"$IP","server_port":${HYSTERIA2_PORT},
   "password":"$PW","obfs":{"type":"salamander","password":"${OBFS_PASSWORD}"},
   "tls":{"enabled":true,"alpn":["h3"],"insecure":true}}]}
EOF
docker rm -f hyt >/dev/null 2>&1
docker run -d --name hyt --network host --entrypoint sing-box -v /tmp/hy.json:/c.json "$IMG" run -c /c.json >/dev/null 2>&1
sleep 4
curl -s --socks5-hostname 127.0.0.1:11090 --max-time 12 https://api.ipify.org; echo   # expect the EXIT node's IP
docker rm -f hyt >/dev/null 2>&1
```

Repeat for each candidate exit. **Only keep the ones that return the exit's IP.** (In the last
incident: work fr-2/de-2/il-1 worked, ie-1/ie-3/ie-4 did not; personal ie-0 worked, nl-0 did not.)

## 3. Apply the fix in the deploy source

**a) `config*.json`** — in the relay's forward group(s), set the working upstreams to `hy2` and drop
the non-working ones. The relay group is `config.proxy[<relay>].features.forward-nonru` (and
`forward-il`). Example (work `work_forward`):

```json
"work_forward": {
  "FR_2_HY2": { "protocol": "hy2", "host": "fr-2.example.org" },
  "DE_2_HY2": { "protocol": "hy2", "host": "de-2.example.org" }
}
```

**b) `vpn/sing-box.json.j2`** — DNS on relays is **aligned with routing** (already in the template;
keep it). All relay-gated on the `relay` flag:
- **dial-time** resolution — `route.default_domain_resolver`, every exit outbound's
  `domain_resolver`, `quad9-doh.domain_resolver`, and `direct-out` — is **`local-dns`**
  (`type:local`, the host resolver). Nothing needed to *bring the tunnel up* may depend on the
  tunnel or on plaintext 9.9.9.9 (see the 2026-08-17 outage below).
- **traffic** resolution still goes through the tunnel: the `dns.rules` fall through to
  `quad9-doh` (DoH, `detour:"auto"`) and `final` is `quad9-doh`, so destination domains resolve
  unpoisoned at the exit. The `domain-ru` DNS rule stays on `local-dns` (RU perspective, works
  with a dead tunnel).
- local DNS on RU relays **is poisoned** (`linkedin/meduza/torproject/facebook` all resolve to one
  sinkhole address). That is fine as long as it is only used for dialing — verify after any DNS
  change by fetching a poisoned domain through the relay and checking for real content, not a
  200-with-block-page (`grep -iE 'ограничен|роскомнадзор'`).

See AGENTS.md → "DNS resolution on relays". No change needed unless you touch DNS.

## 4. Validate, deploy to the relay only, verify

```bash
# validate (see RUNBOOK_deploy.md §"Validate"): render locally + sing-box check → exit=0
make deploy ENV_FILE=$ENVF CONFIG_FILE=$CFG SERVERS_FILE=$SRV TEST_ONLY=<relay>
# verify (see RUNBOOK_deploy.md §"Verify"): logs 0 EOF; end-to-end client test exits via the exit node
```

Expected end state on the relay's rendered `sing-box.json`: outbounds are `hysteria2` to the exits,
`auto` (and `auto-il`) list only working exits, `quad9-doh.detour == "auto"`, and every dial-time
resolver (`route.default_domain_resolver`, each exit outbound's `domain_resolver`,
`quad9-doh.domain_resolver`, `direct-out.domain_resolver`) is `local-dns`. Logs (past the first
~70 s of startup): **0** urltest/reality/dns EOF and no steady-state `direct-out` lookup EOF.

## Notes & escalation

- This is a **workaround, not an unblock** — direct vless-reality RU→EU stays dead. Client→relay
  (domestic RU→RU) is unaffected, which is why the relay itself still accepts clients.
- If a candidate exit fails Hysteria2 too, likely causes: no `hysteria2-in` deployed there
  (redeploy that host), wrong port for its profile, UDP to that IP also filtered.
- **If TSPU starts dropping QUIC/UDP as well:** it already does, per-network and per-destination —
  see the 2026-08-17 incident below. First response is to re-run §2 against *every* candidate exit
  and keep only the ones that answer; only if none do, rotate the exit's IP or add a desync layer
  (zapret / byedpi / GoodbyeDPI-style) on the relay. Neither desync option is wired up here yet.
- **Per-site quirks** (a Russian site that's slow through the tunnel, or a censored site that must
  bypass the DPI): see AGENTS.md → "Per-site routing". RU-IP sites go in the `domain-ru` rule_set
  (direct + local resolve); censored + Cloudflare-fronted sites are pinned to an exit.
- Last applied: 2026-08-24 — personal `ru-0` → **ie-0 + de-2** (a second exit added so the urltest
  finally has something to fail over to); `ru-2` → **ru-0** → those two, because ru-2's network drops
  QUIC to both of those clouds while ru-0's reaches them. work `ru-1` → **am-1 only** (still
  single-exit). Per-site routing lives in `config.routing` (see AGENTS.md).
- Previously: 2026-08-23 — see the incident below.
- Previously: 2026-07-03 — work `ru-1` → fr-2/de-2/am-1/il-1; personal `ru-2` → ie-0.

## Incident 2026-08-17/19 — Hysteria2 blocked to AWS, and a DNS deadlock on top

**What happened.** Both RU relays (`ru-1`, `ru-2`) sit on one small provider, and from that network
Hysteria2/QUIC to **every exit in one large cloud** (fr-2, de-2, ie-1, il-1, us-1, ie-0) stopped establishing — the QUIC handshake is
dropped while *plain* UDP to the same ip:port still arrives (verify with tcpdump on the exit).
Exits elsewhere were unaffected: **am-1** and the RU-domestic `ru-0` both worked, and `ru-0` itself
still reached that cloud fine — so the block is per-source-network, not per-destination.

**Why clients could not even connect.** DNS was chained to the tunnel: `quad9-doh` rode
`detour:"auto"`, and `route.default_domain_resolver` pointed at it. With the tunnel dead, resolving
anything died — including the vless inbound's own REALITY handshake dest:

```
ERROR inbound/vless[vless-in]: TLS handshake: REALITY: failed to dial dest:
      lookup ok.ru: context deadline exceeded          # ~1000/hour on ru-1
```

So the relay stopped accepting clients at all, not just non-RU traffic. On `ru-2` plaintext
`9.9.9.9:53/udp` was blocked too, which killed the `bootstrap` resolver the exit outbounds used.

**Fix applied.** Working exits only (`work_forward` → am-1; personal `ru-2` → new `forward-via-ru0`
group so it hops through `ru-0`, which still reaches ie-0 — note `forward-nonru` is shared with
`ru-0` itself, so a separate group is required to avoid a self-loop), `forward-il` dropped from
`ru-1` (no live IL upstream; `.il` falls back to `direct-out`), plus all **dial-time** resolvers
moved to `local-dns` (§3b) so a dead tunnel can never again take the inbound down with it.

**Deploy gotcha.** A relay whose tunnel is down cannot pull/build from Docker Hub (the docker proxy
drop-in points into the dead tunnel), so `make deploy` fails at *Build docker-compose apps* after
having already written the new configs. Recover by restarting sing-box alone with the new config,
then re-running the deploy:

```bash
ssh <relay> 'cd /root/vpn && docker compose restart sing-box'   # tunnel comes up
make deploy ENV_FILE=$ENVF CONFIG_FILE=$CFG SERVERS_FILE=$SRV TEST_ONLY=<relay>
```
