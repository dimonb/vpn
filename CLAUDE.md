# Claude Code Instructions for VPN Deploy Project

## Project Overview

This is a VPN deployment project with:
- **Ansible** for server provisioning
- **Docker** for containerization
- **Sing-Box** as VPN backend
- **Caddy** for TLS/reverse proxy
- **Python cfgapp** for proxy configuration management
- **NetworkCompactor** for IP range optimization

## Read First (operational knowledge)

- `AGENTS.md` — traffic path, DNS model on relays, secrets/ports, gotchas. **Read before touching deploy, sing-box, or DNS.**
- `doc/RUNBOOK_deploy.md` — deploy / validate / render / add-remove user
- `doc/RUNBOOK_dpi_failover.md` — "VPN dead from Russia" (DPI/TSPU) → exit failover; includes the throwaway-client test recipe

## Project Structure

```
vpn/
├── vpn/cfgapp/           # Python configuration app
│   ├── src/              # Source code
│   │   └── utils.py      # NetworkCompactor + IPProcessor
│   ├── tests/            # Test suite
│   └── .venv/            # Python virtual environment
├── playbooks/            # Ansible playbooks
├── roles/                # Ansible roles
├── templates/            # Jinja2 templates
├── doc/                  # Project documentation
└── Makefile              # Build automation

Archives (can be deleted):
├── _archive_compact/     # Experimental compactor versions
└── _archive_tests/       # Old reality tests
```

## Key Rules

### 1. Python Environment

**Always use the project's virtual environment:**
```bash
cd vpn/cfgapp
source .venv/bin/activate
# OR use directly:
./vpn/cfgapp/.venv/bin/python
```

### 2. Testing

**Run tests before committing:**
```bash
cd vpn/cfgapp
pytest tests/ -v
```

**For NetworkCompactor specifically:**
```bash
pytest tests/test_compactor.py -v
```

### 3. NetworkCompactor Usage

The `NetworkCompactor` class in `vpn/cfgapp/src/utils.py` is the **production version**.

**DO NOT modify archived files** in `_archive_compact/` - they are kept for reference only.

**Use NetworkCompactor like this:**
```python
from src.utils import compact_ipv4_networks

# Compact IPv4 networks
result = compact_ipv4_networks(
    cidrs,
    target_max=200,   # Target network count
    min_prefix=11     # Max /11 networks (2M IPs)
)
```

### 4. CLI Tools

**Network Compaction CLI:**
```bash
cd vpn/cfgapp
python compact_networks.py input.txt output.txt \
    --target 200 \
    --min-prefix 11 \
    --verify \
    --stats
```

### 5. Ansible & Deployment

**Ansible is not on PATH** — it lives in a repo-local venv:
```bash
export PATH="$PWD/.venv-ansible/bin:$PATH"   # ansible-core + bcrypt<4.1 + passlib
```
Collections needed: **`ansible.posix`** (`synchronize`) *and* **`community.general`** (`modprobe`).
A brand-new host needs its key first — `ssh-keyscan -T 10 <host> >> ~/.ssh/known_hosts` — otherwise
every task dies with `Host key verification failed`.

**Inventory is `servers.cfg` (personal) / `servers.work.cfg` (work)** — there is no `hosts.yml`.
Always pass a full profile triple, and `TEST_ONLY` to limit to one host:
```bash
make install-docker                          # install Docker on remote hosts
make deploy ENV_FILE=.env.work CONFIG_FILE=config.work.json SERVERS_FILE=servers.work.cfg TEST_ONLY=ru-1
```
No `make logs` target — read logs over ssh (`docker logs --since 10m vpn-sing-box-1`); the SSH user is per-profile (`root` or `ubuntu`+`sudo`), see the inventory.

### 6. Code Style

**Python:**
- Follow PEP 8
- Use type hints where appropriate
- Document complex algorithms
- Keep functions focused and small

**Tests:**
- Write tests for new functionality
- Maintain 100% coverage for critical paths
- Use fixtures for test data (`tests/fixtures/`)

### 7. Documentation

**Update documentation when:**
- Adding new features
- Changing APIs
- Modifying configuration options

**Documentation locations:**
- `README.md` - Main project documentation
- `doc/README_COMPACTOR.md` - NetworkCompactor API
- `doc/INTEGRATION_SUMMARY.md` - Integration notes
- Inline docstrings in Python code

**This repo is public — split what you write.** Anything committed here (docs, examples, test
fixtures, template defaults) must make sense to a stranger: commands, failure modes, config
semantics, with roles and placeholders (`example.net`, `<profile>`, `<exit host>`) instead of real
names. Concrete infrastructure — host names, providers, regions, IPs, profile suffixes, credential
paths, per-site routing preferences — belongs in the gitignored `.claude.local.md`, with only a
pointer left here. If a template or code default needs an operator-specific value, make it
config/env-driven with an empty default rather than baking the value in.

### 8. Git & Commits

**Commit message format:**
```
type: short description

Longer description if needed

Examples:
- feat: add IPv6 support to NetworkCompactor
- fix: correct coverage calculation in verify_coverage
- docs: update README with CLI examples
- test: add integration tests for real AWS data
- refactor: simplify supernet finding algorithm
```

**Before committing:**
1. Run tests: `pytest tests/ -v`
2. Check for obvious issues
3. Update documentation if needed

### 9. NetworkCompactor - Important Notes

**Key characteristics:**
- ✅ Guarantees 100% coverage of original networks
- ✅ Adaptive algorithm with cost thresholds
- ✅ Supports both IPv4 and IPv6
- ✅ Production-ready and tested

**Parameters:**
- `target_max`: Target number of networks (approximate)
- `min_prefix`: Minimum prefix length (maximum network size)
  - IPv4: 8-32 (8=/8=16M IPs, 11=/11=2M IPs, 12=/12=1M IPs)
  - IPv6: 8-128 (typically 32=/32)

**Proven results:**
- AWS (1633 nets → 199): 87.8% reduction, 3.00x coverage
- Google (97 nets → 46): 52.6% reduction, 2.26x coverage

### 10. Common Tasks

**Adding new IP ranges:**
1. Add to appropriate `.netset` or data file
2. Test with NetworkCompactor if needed
3. Run integration tests
4. Update documentation

**Modifying NetworkCompactor:**
1. Make changes in `vpn/cfgapp/src/utils.py`
2. Update tests in `tests/test_compactor.py`
3. Run full test suite
4. Update `doc/README_COMPACTOR.md`
5. **Never** modify archived files

**Deploying to servers:**
1. Configure `.env` with server details
2. Test connection: `ansible all -m ping`
3. Run deployment: `make deploy`
4. Check logs: `make logs`

### 11. Troubleshooting

**Tests failing:**
- Check Python environment: `which python`
- Reinstall dependencies: `poetry install`
- Clear pytest cache: `rm -rf .pytest_cache`

**NetworkCompactor issues:**
- Verify input format (one CIDR per line)
- Check parameters (min_prefix must be ≤ network prefix)
- Use `--verify` flag to check coverage

**Ansible issues:**
- Check SSH connectivity
- Verify inventory file
- Check `.env` configuration
- Review playbook syntax: `ansible-playbook --syntax-check playbook.yml`

### 12. Gotchas That Cost Time

- `.env*`, `config.json`, `config.work.json`, `servers*.cfg` are **gitignored local secrets** — edits there never appear in `git status`/`git diff`.
- Clients enter on **:443** (caddy layer4 routes by TLS SNI → sing-box vless-in :8443, xray :28443). Port 8443 is not reachable externally — end-to-end tests must target :443.
- Validate a rendered template without deploying: `ansible <host> -i <inv> -e "salt=…" -m debug -a 'msg={{ lookup("template","vpn/sing-box.json.j2") }}'`
- A relay whose tunnel is down cannot pull from Docker Hub, so `make deploy` fails at *Build docker-compose apps* **after** writing new configs — `docker compose restart sing-box` on the relay, then re-run the deploy.
- A full disk fails **silently** here (`scp` → `write remote … Failure`, `tic` doing nothing at all). Check `df -h /` early; `docker builder prune -af` is the usual win. Never `system prune -a` on a RU host.
- A `urltest` pool with one member has **no failover** — one upstream hiccup is a total outage. Before blaming a relay, count the exits in its forward group.

### 13. Adding a VPN host

1. Inventory line in `servers.cfg` / `servers.work.cfg` (gitignored, local only).
2. `subs` entry in `config.json` / `config.work.json` (gitignored): put it in a relay's forward
   group to make it an upstream, in a client group to advertise it to clients.
3. **DNS A record must resolve before the deploy** — caddy takes an ACME cert on the host name, so
   a missing record fails the run. (Where the zone is managed: see local notes / `AGENTS.md`.)
4. Add it to host monitoring, or it is invisible when it dies.
5. `make install-docker TEST_ONLY=<host>` → `make deploy TEST_ONLY=<host>`.

Cloud-provider quirks (missing public IP, layered firewalls, Minimal images without `rsync`, swap
on 1 GB shapes) are collected in `AGENTS.md`.

## Additional Resources

- **Main README**: [README.md](README.md)
- **Operations**: [AGENTS.md](AGENTS.md)
- **Deploy runbook**: [doc/RUNBOOK_deploy.md](doc/RUNBOOK_deploy.md)
- **DPI failover runbook**: [doc/RUNBOOK_dpi_failover.md](doc/RUNBOOK_dpi_failover.md)
- **NetworkCompactor API**: [doc/README_COMPACTOR.md](doc/README_COMPACTOR.md)
- **Integration Guide**: [doc/INTEGRATION_SUMMARY.md](doc/INTEGRATION_SUMMARY.md)
- **Reality Setup**: [doc/REALITY_SETUP.md](doc/REALITY_SETUP.md)

## Quick Reference

### File Locations
- Production code: `vpn/cfgapp/src/`
- Tests: `vpn/cfgapp/tests/`
- Test data: `vpn/cfgapp/tests/fixtures/`
- CLI tools: `vpn/cfgapp/*.py`
- Documentation: `doc/`
- Archives: `_archive_*/` (can be deleted)

### Environment
- Python venv (cfgapp): `vpn/cfgapp/.venv/`
- Ansible venv: `./.venv-ansible/` (not on PATH by default)
- Make: System-wide

### Priority Files
- `vpn/cfgapp/src/utils.py` - Core utilities + NetworkCompactor
- `vpn/cfgapp/tests/test_compactor.py` - Compactor tests
- `Makefile` - Build automation
- `.env` - Configuration (not in git)

---

**Last Updated**: August 24, 2026
**Project Status**: Active
