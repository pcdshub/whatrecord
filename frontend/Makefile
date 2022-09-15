ifneq ("$(wildcard ../docker/.env)","")
	include ../docker/.env
endif
ifneq ("$(wildcard ../docker/.env.local)","")
	include ../docker/.env.local
endif

API_HOST      ?= localhost
API_PORT      ?= 8895
FRONTEND_PORT ?= 8896

dev:
	@echo "* Starting up the dev server on port ${FRONTEND_PORT} with yarn..."
	@echo "* Expecting 'whatrec server' to be running on ${API_HOST}:${API_PORT}"
	@echo "* (see .env or .env.local to customize this)"
	yarn serve --port "${FRONTEND_PORT}"

dev-setup:
	yarn install

docker-dev:
	@echo "* Starting up the dev server via docker on port ${FRONTEND_PORT}..."
	@echo "* Expecting 'whatrec server' to be running on ${API_HOST}:${API_PORT}"
	@echo "* (see .env or .env.local to customize this)"
	docker run -it --rm \
		--name whatrecord-frontend-dev \
		-v "$(PWD)":/usr/src/app \
		-w /usr/src/app \
		-p $(FRONTEND_PORT):$(FRONTEND_PORT) \
		node:18.9-alpine \
		yarn serve --port "$(FRONTEND_PORT)"

prod:
	yarn build

clean:
	rm -rf ./dist ./node_modules

.PHONY: dev dev-setup prod clean
