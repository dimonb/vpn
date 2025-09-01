SHELL := /bin/bash
URL := "https://rohoscsnhb.execute-api.eu-west-1.amazonaws.com/default/vpn"

# Profile Configuration Examples:
# make deploy ENV_FILE=.env.prod CONFIG_FILE=config.prod.json SERVERS_FILE=servers.prod.cfg
# make cfgapp-dev ENV_FILE=.env.dev CONFIG_FILE=config.dev.json
# make deploy-test ENV_FILE=.env.test CONFIG_FILE=config.test.json SERVERS_FILE=servers.test.cfg
# make passwords CONFIG_FILE=config.backup.json

# Profile configuration - alternative file names
ENV_FILE ?= ".env"

# Load environment variables from .env file
ifneq (,$(wildcard ./$(ENV_FILE)))
    include $(ENV_FILE)
    export SALT OBFS_PASSWORD METRICS_PWD BASE_URL
endif

# Default values if .env file doesn't exist
HTTP_PORT ?= "80"
HTTPS_PORT ?= "443"
HYSTERIA2_PORT ?= "47012"
HYSTERIA2_V2_PORT ?= "47013"
CONFIG_HOST ?= "fake.host"

CONFIG_FILE ?= "config.json"
SERVERS_FILE ?= "servers.cfg"

.PHONY: install-docker check-env deploy deploy-test cn passwords

install-docker:
	ansible-playbook -i $(SERVERS_FILE) --ssh-extra-args='-o ControlPersist=60s' -f 4 install_docker.yml

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
	echo "Using ports - HTTP: $(HTTP_PORT), HTTPS: $(HTTPS_PORT), Hysteria2: $(HYSTERIA2_PORT), Hysteria2-v2: $(HYSTERIA2_V2_PORT)"

deploy: check-env
	@source $(ENV_FILE) 2>/dev/null || true; \
	ansible-playbook -i $(SERVERS_FILE) --ssh-extra-args='-o ControlPersist=60s' -f 4 deploy_vpn.yml -e "salt=$${SALT:-}" -e "obfs_password=$${OBFS_PASSWORD:-}" -e "http_port=$(HTTP_PORT)" -e "https_port=$(HTTPS_PORT)" -e "hysteria2_port=$(HYSTERIA2_PORT)" -e "hysteria2_v2_port=$(HYSTERIA2_V2_PORT)" -e "config_host=$(CONFIG_HOST)" -e "metrics_pwd=$${METRICS_PWD:-}" -e "config_file=$(CONFIG_FILE)"


cfgapp-dev:
	@source $(ENV_FILE) 2>/dev/null || true; \
	cfg_path=$$(pwd)/$(CONFIG_FILE); \
	cd vpn/cfgapp && BASE_URL=$${BASE_URL:-} OBFS_PASSWORD=$${OBFS_PASSWORD:-} PROXY_CONFIG=$$cfg_path HYSTERIA2_PORT=$(HYSTERIA2_PORT) HYSTERIA2_V2_PORT=$(HYSTERIA2_V2_PORT) SALT=$${SALT:-} CONFIG_HOST=$(CONFIG_HOST) .venv/bin/poetry run python -m src.main

deploy-test:
	@source $(ENV_FILE) 2>/dev/null || true; \
	ansible-playbook -i $(SERVERS_FILE) --ssh-extra-args='-o ControlPersist=60s' -f 4 --limit de-1 deploy_vpn.yml -e "salt=$${SALT:-}" -e "obfs_password=$${OBFS_PASSWORD:-}" -e "http_port=$(HTTP_PORT)" -e "https_port=$(HTTPS_PORT)" -e "hysteria2_port=$(HYSTERIA2_PORT)" -e "hysteria2_v2_port=$(HYSTERIA2_V2_PORT)" -e "config_host=$(CONFIG_HOST)" -e "metrics_pwd=$${METRICS_PWD:-}" -e "config_file=$(CONFIG_FILE)"

cn:
	@echo "Generating hash for: $(NAME)"
	@hash=$$(echo -n "$(NAME).$(SALT)" | md5sum | awk '{print $$1}'); \
	echo "Full hash: $$hash"; \
	formatted=$$(echo "$$hash" | cut -c1-8)-$$(echo "$$hash" | cut -c9-12)-$$(echo "$$hash" | cut -c13-16)-$$(echo "$$hash" | cut -c17-20)-$$(echo "$$hash" | cut -c21-32); \
	echo "Formatted hash: $$formatted"; \
	qq=$$(echo -e "$(URL)?name=$(NAME)&sn=$$hash&ws=yes" | base64); \
	echo "SUB: $(URL)?name=$(NAME)&sn=$$hash&ws=yes"; \
	echo sub://$$qq"#ebac.ws" | qrencode -t PNG32 -o ~/Downloads/$(NAME).png; \
	echo "QR: ~/Downloads/$(NAME).png"; \
	email_exists=$$(jq -r --arg NAME "$(NAME)@" '.inbounds[0].settings.clients[] | select(.email == $$NAME) | .email' v2ray/v2ray-server.json); \
	if [ -z "$$email_exists" ]; then \
		jq --arg NAME "$(NAME)@" --arg UID "$$formatted" '.inbounds[0].settings.clients += [{"email": $$NAME, "id": $$UID, "level": 0, "alterId": 64}]' v2ray/v2ray-server.json > temp.json && mv temp.json v2ray/v2ray-server.json; \
		echo "Added new client to v2ray/v2ray-server.json"; \
	else \
		echo "Client with email $(NAME) already exists"; \
	fi

passwords:
	@source $(ENV_FILE) 2>/dev/null || true; \
	set -e; \
	if [ -z "$${SALT:-}" ]; then echo "ERROR: SALT is not set. Create .env from env.example and set SALT"; exit 1; fi; \
	echo "Using ports - HTTP: $(HTTP_PORT), HTTPS: $(HTTPS_PORT), Hysteria2: $(HYSTERIA2_PORT), Hysteria2-v2: $(HYSTERIA2_V2_PORT)"; \
	if command -v sha256sum >/dev/null 2>&1; then HASH="sha256sum"; \
	elif command -v shasum >/dev/null 2>&1; then HASH="shasum -a 256"; \
	else echo "ERROR: sha256 utility not found (install coreutils or use shasum)"; exit 1; fi; \
	jq -r '.users[]' $(CONFIG_FILE) | while read -r user; do \
	  pass=$$(printf "%s" "$$user.$${SALT:-}" | $$HASH | awk '{print $$1}'); \
	  echo "$$user: $$pass"; \
	done

