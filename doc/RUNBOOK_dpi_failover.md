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

Run from the **relay** (the RU box). `$UP` = an upstream/exit host (e.g. `fr-2.outline.ebac.dev`).

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
`$HYSTERIA2_PORT` (ebac 47024, dimonb 47012). Use the exit's IP.

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
incident: ebac fr-2/de-2/il-1 worked, ie-1/ie-3/ie-4 did not; dimonb ie-0 worked, nl-0 did not.)

## 3. Apply the fix in the deploy source

**a) `config*.json`** — in the relay's forward group(s), set the working upstreams to `hy2` and drop
the non-working ones. The relay group is `config.proxy[<relay>].features.forward-nonru` (and
`forward-il`). Example (ebac `ebac_forward`):

```json
"ebac_forward": {
  "FR_2_HY2": { "protocol": "hy2", "host": "fr-2.outline.ebac.dev" },
  "DE_2_HY2": { "protocol": "hy2", "host": "de-2.outline.ebac.dev" }
}
```

**b) `vpn/sing-box.json.j2`** — DNS on relays is **aligned with routing** (already in the template;
keep it). All relay-gated on `forward_group`:
- `route.default_domain_resolver` = **`quad9-doh`** (DoH with `detour:"auto"`) → tunnel-routed names
  resolve **through the tunnel**, unpoisoned. (Was `bootstrap`; plaintext 9.9.9.9 from RU is DPI-
  disrupted, which mis-resolved foreign domains and misrouted them to `direct-out` → floods of
  `open connection to <domain>… using outbound/direct[direct-out]: lookup …: unexpected EOF`.)
- each exit outbound has **`domain_resolver:"bootstrap"`** (udp 9.9.9.9) → exit **server addresses**
  resolve directly so the tunnel always comes up (no "resolve the tunnel through the tunnel" deadlock).
- `direct-out` and the `domain-ru` DNS rule use **`local-dns`** (`type:local`) → direct-routed names
  resolve from the RU perspective, work even if the tunnel is down.
See AGENTS.md → "DNS resolution on relays". No change needed unless you touch DNS.

## 4. Validate, deploy to the relay only, verify

```bash
# validate (see RUNBOOK_deploy.md §"Validate"): render locally + sing-box check → exit=0
make deploy ENV_FILE=$ENVF CONFIG_FILE=$CFG SERVERS_FILE=$SRV TEST_ONLY=<relay>
# verify (see RUNBOOK_deploy.md §"Verify"): logs 0 EOF; end-to-end client test exits via the exit node
```

Expected end state on the relay's rendered `sing-box.json`: outbounds are `hysteria2` to the exits,
`auto` (and `auto-il`) list only working exits, `quad9-doh.detour == "auto"`,
`route.default_domain_resolver == {"server":"quad9-doh"}`, each exit outbound has
`domain_resolver == "bootstrap"`, and `direct-out.domain_resolver == "local-dns"`. Logs (past the
first ~70 s of startup): **0** urltest/reality/dns EOF and no steady-state `direct-out` lookup EOF.

## Notes & escalation

- This is a **workaround, not an unblock** — direct vless-reality RU→EU stays dead. Client→relay
  (domestic RU→RU) is unaffected, which is why the relay itself still accepts clients.
- If a candidate exit fails Hysteria2 too, likely causes: no `hysteria2-in` deployed there
  (redeploy that host), wrong port for its profile, UDP to that IP also filtered.
- **If TSPU starts dropping QUIC/UDP as well:** options are rotating the exit's IP, or adding a
  desync layer (zapret / byedpi / GoodbyeDPI-style) on the relay. Neither is wired up here yet.
- **Per-site quirks** (a Russian site that's slow through the tunnel, or a censored site that must
  bypass the DPI): see AGENTS.md → "Per-site routing". RU-IP sites go in the `domain-ru` rule_set
  (direct + local resolve); censored + Cloudflare-fronted sites are pinned to an exit.
- Last applied: 2026-07-03 — ebac `ru-1` → fr-2/de-2/**am-1**/il-1; dimonb `ru-2` → ie-0. DNS
  aligned with routing on both relays; `fanfics.me`→direct, `ficbook.net`→am-1 (ebac).
