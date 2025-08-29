SHELL := /bin/bash
URL := "https://rohoscsnhb.execute-api.eu-west-1.amazonaws.com/default/vpn"

# Load environment variables from .env file
ifneq (,$(wildcard ./.env))
    include .env
    export
endif

# Default values if .env file doesn't exist
SALT ?= ""
OBFS_PASSWORD ?= ""
HTTP_PORT ?= "80"
HTTPS_PORT ?= "443"
HYSTERIA2_PORT ?= "47012"
CONFIG_HOST ?= "fake.host"

.PHONY: install-docker check-env deploy deploy-test cn passwords

install-docker:
	ansible-playbook -i servers.cfg --ssh-extra-args='-o ControlPersist=60s' -f 4 install_docker.yml

check-env:
	@if [ -z "$(SALT)" ]; then \
		echo "ERROR: SALT is not set. Please create .env file from env.example and set SALT value"; \
		exit 1; \
	fi
	@if [ -z "$(OBFS_PASSWORD)" ]; then \
		echo "ERROR: OBFS_PASSWORD is not set. Please create .env file from env.example and set OBFS_PASSWORD value"; \
		exit 1; \
	fi
	@echo "Using ports - HTTP: $(HTTP_PORT), HTTPS: $(HTTPS_PORT), Hysteria2: $(HYSTERIA2_PORT)"

deploy: check-env
	ansible-playbook -i servers.cfg --ssh-extra-args='-o ControlPersist=60s' -f 4 deploy_vpn.yml -e "salt=$(SALT)" -e "obfs_password=$(OBFS_PASSWORD)" -e "http_port=$(HTTP_PORT)" -e "https_port=$(HTTPS_PORT)" -e "hysteria2_port=$(HYSTERIA2_PORT)" -e "config_host=$(CONFIG_HOST)"


cfgapp-dev:
	@cfg_path=$$(pwd)/config.json; \
	cd vpn/cfgapp && OBFS_PASSWORD=$(OBFS_PASSWORD) PROXY_CONFIG=$$cfg_path HYSTERIA2_PORT=$(HYSTERIA2_PORT) SALT=$(SALT) CONFIG_HOST=$(CONFIG_HOST) .venv/bin/poetry run python -m src.main

deploy-test:
	ansible-playbook -i servers.cfg --ssh-extra-args='-o ControlPersist=60s' -f 4 --limit de-1 deploy_v2ray.yml

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
	@set -e; \
	if [ -z "$(SALT)" ]; then echo "ERROR: SALT is not set. Create .env from env.example and set SALT"; exit 1; fi; \
	echo "Using ports - HTTP: $(HTTP_PORT), HTTPS: $(HTTPS_PORT), Hysteria2: $(HYSTERIA2_PORT)"; \
	if command -v sha256sum >/dev/null 2>&1; then HASH="sha256sum"; \
	elif command -v shasum >/dev/null 2>&1; then HASH="shasum -a 256"; \
	else echo "ERROR: sha256 utility not found (install coreutils or use shasum)"; exit 1; fi; \
	jq -r '.users[]' config.json | while read -r user; do \
	  pass=$$(printf "%s" "$$user.$(SALT)" | $$HASH | awk '{print $$1}'); \
	  echo "$$user: $$pass"; \
	done

