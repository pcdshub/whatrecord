ifneq ("$(wildcard ../docker/.env)","")
	include ../docker/.env
endif
ifneq ("$(wildcard ../docker/.env.local)","")
	include ../docker/.env.local
endif
ifneq ("$(wildcard ./.env)","")
	include ./.env
endif
ifneq ("$(wildcard ./.env.local)","")
	include ./.env.local
endif

WHATRECORD_API_HOST      ?= localhost
WHATRECORD_API_PORT      ?= 8895
WHATRECORD_FRONTEND_PORT ?= 8896

_show_settings:
	@echo "* Starting up the dev server on port ${WHATRECORD_FRONTEND_PORT} with yarn..."
	@echo "* Expecting the whatrecord backend to be running on ${WHATRECORD_API_HOST}:${WHATRECORD_API_PORT}"
	@echo "* (see .env or .env.local to customize this)"

dev: _show_settings
	yarn build --mode=development
	yarn serve --port "${WHATRECORD_FRONTEND_PORT}" --host --strictPort --mode=development

dev-watch:
	@echo "Building and monitoring source files for changes..."
	yarn build --mode=development --minify=false --watch

dev-setup:
	yarn install

docker-dev: _show_settings
	docker run -it --rm \
		--name whatrecord-frontend-dev \
		-v "$(PWD)":/usr/src/app \
		-w /usr/src/app \
		-p $(WHATRECORD_FRONTEND_PORT):$(WHATRECORD_FRONTEND_PORT) \
		node:18.9-alpine \
		yarn serve --port "$(WHATRECORD_FRONTEND_PORT)"

prod:
	yarn build

clean:
	rm -rf ./dist ./node_modules

.PHONY: _show_settings dev dev-watch dev-setup prod clean
