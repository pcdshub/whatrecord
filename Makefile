all: install local-server

IPY_OPTS ?= -i
GATEWAY_CONFIG ?= /reg/g/pcds/gateway/config/
STARTUP_SCRIPTS ?= ./whatrecord/tests/iocs/*/st.cmd

# Frontend expects the server to run on a specific port; check its settings
# here (or use the default below)
ifneq ("$(wildcard ./frontend/.env)","")
	include frontend/.env
endif
ifneq ("$(wildcard ./frontend/.env.local)","")
	include frontend/.env.local
endif

API_PORT ?= 8898

install:
	pip install .

docker-example:
	cd docker && \
		docker-compose up

local-server:
	@echo "Running server with:"
	@echo " - Gateway config: ${GATEWAY_CONFIG}"
	@echo " - Startup scripts: ${STARTUP_SCRIPTS}"
	@echo " - API Port: ${API_PORT}"
	@echo " - Extra arguments: ${SERVER_ARGS}"
	ipython -i -m whatrecord.bin.main -- server \
		--gateway-config $(GATEWAY_CONFIG) \
		--scripts $(STARTUP_SCRIPTS) \
		--port $(API_PORT) \
		$(SERVER_ARGS)

.phony: install local-server docker-example
