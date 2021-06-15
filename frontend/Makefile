VUE_PORT=8899

dev:
	@echo "* Starting up the dev server on port ${VUE_PORT} with yarn..."
	@echo "* Expecting 'whatrec server' to be running on port 8080"
	@echo "* (see vue.config.js to customize this)"
	yarn serve --port "${VUE_PORT}"

prod:
	yarn build

clean:
	rm -rf ./dist ./node_modules
