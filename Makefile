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

deploy: check-env
	ansible-playbook -i servers.cfg --ssh-extra-args='-o ControlPersist=60s' -f 4 deploy_vpn.yml -e "salt=$(SALT)" -e "obfs_password=$(OBFS_PASSWORD)"

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

