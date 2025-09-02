SHELL := /bin/bash
URL := "https://rohoscsnhb.execute-api.eu-west-1.amazonaws.com/default/vpn"

# Profile Configuration Examples:
# make deploy ENV_FILE=.env.prod CONFIG_FILE=config.prod.json SERVERS_FILE=servers.prod.cfg
# make cfgapp-dev ENV_FILE=.env.dev CONFIG_FILE=config.dev.json
# make deploy-test ENV_FILE=.env.test CONFIG_FILE=config.test.json SERVERS_FILE=servers.test.cfg
# make passwords CONFIG_FILE=config.backup.json
# make deploy TEST_ONLY=br-1  # Test on specific instance only

# Profile configuration - alternative file names
ENV_FILE ?= ".env"

# Load environment variables from .env file
ifneq (,$(wildcard ./$(ENV_FILE)))
    include $(ENV_FILE)
    export SALT OBFS_PASSWORD METRICS_PWD BASE_URL REALITY_PRIVATE_KEY REALITY_PUBLIC_KEY REALITY_SHORT_ID
endif

# Default values if .env file doesn't exist
HTTP_PORT ?= "80"
HTTPS_PORT ?= "443"
HYSTERIA2_PORT ?= "47012"
HYSTERIA2_V2_PORT ?= "47013"
VLESS_PORT ?= "8443"
REALITY_PRIVATE_KEY ?= "your-reality-private-key-here"
REALITY_PUBLIC_KEY ?= "your-reality-public-key-here"
REALITY_SHORT_ID ?= "c047f3e99c90ff71"
CONFIG_HOST ?= "fake.host"

CONFIG_FILE ?= "config.json"
SERVERS_FILE ?= "servers.cfg"

# Test mode - limit to specific instance
TEST_ONLY ?= ""

# Common Ansible arguments
ANSIBLE_ARGS := -i $(SERVERS_FILE) --ssh-extra-args='-o ControlPersist=60s'$(if $(filter-out "",$(TEST_ONLY)), --limit $(TEST_ONLY),)
ANSIBLE_ENV_ARGS := -e "salt=$${SALT:-}" -e "obfs_password=$${OBFS_PASSWORD:-}" -e "http_port=$(HTTP_PORT)" -e "https_port=$(HTTPS_PORT)" -e "hysteria2_port=$(HYSTERIA2_PORT)" -e "hysteria2_v2_port=$(HYSTERIA2_V2_PORT)" -e "vless_port=$(VLESS_PORT)" -e "reality_private_key=$(REALITY_PRIVATE_KEY)" -e "reality_public_key=$(REALITY_PUBLIC_KEY)" -e "reality_short_id=$(REALITY_SHORT_ID)" -e "config_host=$(CONFIG_HOST)" -e "metrics_pwd=$${METRICS_PWD:-}" -e "config_file=$(CONFIG_FILE)"

.PHONY: install-docker check-env deploy deploy-test cn passwords

install-docker:
	ansible-playbook $(ANSIBLE_ARGS) -f 4 install_docker.yml

check-env:
	@source $(ENV_FILE) 2>/dev/null || true; \
	if [ -z "$${SALT:-}" ]; then \
		echo "ERROR: SALT is not set. Please create .env file from env.example and set SALT value"; \
		exit 1; \
	fi; \
	if [ -z "$${OBFS_PASSWORD:-}" ]; then \
		echo "ERROR: OBFS_PASSWORD is not set. Please create .env file from env.example and set OBFS_PASSWORD value"; \
		exit 1; \
	fi; \
	if [ -z "$${METRICS_PWD:-}" ]; then \
		echo "ERROR: METRICS_PWD is not set. Please create .env file from env.example and set METRICS_PWD value"; \
		exit 1; \
	fi; \
	if [ -z "$${REALITY_PRIVATE_KEY:-}" ]; then \
		echo "ERROR: REALITY_PRIVATE_KEY is not set. Please create .env file from env.example and set REALITY_PRIVATE_KEY value"; \
		exit 1; \
	fi; \
	if [ -z "$${REALITY_PUBLIC_KEY:-}" ]; then \
		echo "ERROR: REALITY_PUBLIC_KEY is not set. Please create .env file from env.example and set REALITY_PUBLIC_KEY value"; \
		exit 1; \
	fi; \
	if [ -z "$${REALITY_SHORT_ID:-}" ]; then \
		echo "ERROR: REALITY_SHORT_ID is not set. Please create .env file from env.example and set REALITY_SHORT_ID value"; \
		exit 1; \
	fi; \
	echo "Using ports - HTTP: $(HTTP_PORT), HTTPS: $(HTTPS_PORT), Hysteria2: $(HYSTERIA2_PORT), Hysteria2-v2: $(HYSTERIA2_V2_PORT), VLESS: $(VLESS_PORT)"

deploy: check-env
	@source $(ENV_FILE) 2>/dev/null || true; \
	ansible-playbook $(ANSIBLE_ARGS) -f 5 deploy_vpn.yml $(ANSIBLE_ENV_ARGS)

ubuntu-update:
	ansible-playbook $(ANSIBLE_ARGS) -f 4 ubuntu_dist_upgrade.yml

ubuntu-upgrade:
	ansible-playbook $(ANSIBLE_ARGS) -f 4 ubuntu_release_upgrade.yml

cfgapp-dev:
	@source $(ENV_FILE) 2>/dev/null || true; \
	cfg_path=$$(pwd)/$(CONFIG_FILE); \
	cd vpn/cfgapp && BASE_URL=$${BASE_URL:-} OBFS_PASSWORD=$${OBFS_PASSWORD:-} PROXY_CONFIG=$$cfg_path HYSTERIA2_PORT=$(HYSTERIA2_PORT) HYSTERIA2_V2_PORT=$(HYSTERIA2_V2_PORT) VLESS_PORT=$(VLESS_PORT) REALITY_PRIVATE_KEY=$${REALITY_PRIVATE_KEY:-} REALITY_PUBLIC_KEY=$${REALITY_PUBLIC_KEY:-} REALITY_SHORT_ID=$${REALITY_SHORT_ID:-} SALT=$${SALT:-} CONFIG_HOST=$(CONFIG_HOST) .venv/bin/poetry run python -m src.main


passwords:
	@source $(ENV_FILE) 2>/dev/null || true; \
	set -e; \
	if [ -z "$${SALT:-}" ]; then echo "ERROR: SALT is not set. Create .env from env.example and set SALT"; exit 1; fi; \
	echo "Using ports - HTTP: $(HTTP_PORT), HTTPS: $(HTTPS_PORT), Hysteria2: $(HYSTERIA2_PORT), Hysteria2-v2: $(HYSTERIA2_V2_PORT), VLESS: $(VLESS_PORT)"; \
	echo "Reality: $(REALITY_PRIVATE_KEY), $(REALITY_PUBLIC_KEY), $(REALITY_SHORT_ID)"; \
	if command -v sha256sum >/dev/null 2>&1; then HASH="sha256sum"; \
	elif command -v shasum >/dev/null 2>&1; then HASH="shasum -a 256"; \
	else echo "ERROR: sha256 utility not found (install coreutils or use shasum)"; exit 1; fi; \
	jq -r '.users[]' $(CONFIG_FILE) | while read -r user; do \
	  pass=$$(printf "%s" "$$user.$${SALT:-}" | $$HASH | awk '{print $$1}'); \
	  echo "$$user: $$pass"; \
	done

