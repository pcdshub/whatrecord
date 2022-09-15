IMAGE ?= pcdshub/whatrecord:latest
RUN_ARGS ?=
TEST_ARGS ?= pytest --pyargs whatrecord -v
INSPECT_ARGS ?= /bin/bash --login
CACHE_VOLUME_NAME ?= docker_whatrecord-cache
IOC_BINARY ?= $(shell which softIoc)
EXTRA_RUN_ARGS ?= -v "$(CACHE_VOLUME_NAME):/var/lib/whatrecord/cache" -v $(IOC_BINARY):/ioc/softIoc

all: build-image run-test

build-image: Dockerfile
	# docker build --tag $(IMAGE) --file Dockerfile --progress=plain \
	# 		--build-arg PIP_EXTRAS="$(PIP_EXTRAS)" \
	# 		$(PWD)/../
	docker-compose build whatrecord

	@echo "Assuming you have an IOC under the working directory:"
	@echo "$ docker run -v \$${PWD}:/ioc -it $(IMAGE) whatrecord parse iocBoot/ioc-*/st.cmd"

run-whatrecord:
	docker run -it $(EXTRA_RUN_ARGS) $(IMAGE) $(RUN_ARGS)

run-test:
	docker run -it $(EXTRA_RUN_ARGS) $(IMAGE) $(TEST_ARGS)

inspect:
	docker run -it $(EXTRA_RUN_ARGS) $(IMAGE) $(INSPECT_ARGS)

gdb-info:
	if [ ! -f "$(IOC_BINARY)" ]; then \
		echo "Try make gdb-info IOC_BINARY=/path/to/linux-x86_64/softIoc"; exit 1; \
	fi
	echo "Running gdb-info on host file: $(IOC_BINARY)"
	docker run -it -v $(IOC_BINARY):/ioc/softIoc \
		$(IMAGE) \
		gdb \
		--batch-silent \
		--command /usr/local/src/whatrecord/whatrecord/plugins/gdb_binary_info.py \
		--args /ioc/softIoc

.PHONY: all build-image run-whatrecord run-test inspect clear-cache gdb-info
