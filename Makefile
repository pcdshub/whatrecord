all: install server

IPY_OPTS ?= -i
GATEWAY_CONFIG ?= /reg/g/pcds/gateway/config/
STARTUP_SCRIPTS ?=

# Frontend expects the server to run on a specific port; check its settings
# here (or use the default below)
ifneq ("$(wildcard ./frontend/.env)","")
	include frontend/.env
endif
ifneq ("$(wildcard ./frontend/.env.local)","")
	include frontend/.env.local
endif

API_PORT ?= 8898


MACOSX_DEPLOYMENT_TARGET ?= 10.9

install:
	MACOSX_DEPLOYMENT_TARGET=$(MACOSX_DEPLOYMENT_TARGET) pip install  .

frontend-release:
	# npm install -g vue@next @vue/cli
	(cd frontend && yarn build) || exit 1
	mkdir -p src/whatrecord/server/static/{js,img,css}
	cp -R frontend/dist/js/* src/whatrecord/server/static/js/
	cp -R frontend/dist/img/* src/whatrecord/server/static/img/
	cp -R frontend/dist/css/* src/whatrecord/server/static/css/
	cp frontend/dist/favicon.ico src/whatrecord/server/static/
	cp -R frontend/dist/ src/whatrecord/server/static/css/

server:
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

.phony: install ipython server profile time frontend-release
