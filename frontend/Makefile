ifneq ("$(wildcard ./.env)","")
	include .env
endif
ifneq ("$(wildcard ./.env.local)","")
	include .env.local
endif

API_HOST      ?= localhost
API_PORT      ?= 8895
FRONTEND_PORT ?= 8896

dev:
	@echo "* Starting up the dev server on port ${FRONTEND_PORT} with yarn..."
	@echo "* Expecting 'whatrec server' to be running on ${API_HOST}:${API_PORT}"
	@echo "* (see .env or .env.local to customize this)"
	yarn serve --port "${FRONTEND_PORT}"

prod:
	yarn build

clean:
	rm -rf ./dist ./node_modules
