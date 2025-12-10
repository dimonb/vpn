# Claude Code Instructions for VPN Deploy Project

## Project Overview

This is a VPN deployment project with:
- **Ansible** for server provisioning
- **Docker** for containerization
- **Sing-Box** as VPN backend
- **Caddy** for TLS/reverse proxy
- **Python cfgapp** for proxy configuration management
- **NetworkCompactor** for IP range optimization

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

**Before running Ansible:**
- Ensure `.env` file is configured
- Check inventory in `hosts.yml` or `hosts`
- Test connection: `ansible all -m ping`

**Common Make targets:**
```bash
make install-docker    # Install Docker on remote hosts
make deploy           # Deploy VPN services
make logs             # View service logs
```

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

## Additional Resources

- **Main README**: [README.md](README.md)
- **NetworkCompactor API**: [doc/README_COMPACTOR.md](doc/README_COMPACTOR.md)
- **Integration Guide**: [doc/INTEGRATION_SUMMARY.md](doc/INTEGRATION_SUMMARY.md)
- **Reality Setup**: [REALITY_SETUP.md](REALITY_SETUP.md)

## Quick Reference

### File Locations
- Production code: `vpn/cfgapp/src/`
- Tests: `vpn/cfgapp/tests/`
- Test data: `vpn/cfgapp/tests/fixtures/`
- CLI tools: `vpn/cfgapp/*.py`
- Documentation: `doc/`
- Archives: `_archive_*/` (can be deleted)

### Environment
- Python venv: `vpn/cfgapp/.venv/`
- Ansible: System-wide or in separate venv
- Make: System-wide

### Priority Files
- `vpn/cfgapp/src/utils.py` - Core utilities + NetworkCompactor
- `vpn/cfgapp/tests/test_compactor.py` - Compactor tests
- `Makefile` - Build automation
- `.env` - Configuration (not in git)

---

**Last Updated**: December 9, 2024
**Project Status**: Active, NetworkCompactor integrated and tested ✅
