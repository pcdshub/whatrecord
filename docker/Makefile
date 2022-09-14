IMAGE ?= pcdshub/whatrecord:latest
RUN_ARGS ?=
TEST_ARGS ?= pytest --pyargs whatrecord -v
INSPECT_ARGS ?= /bin/bash --login
EXTRA_RUN_ARGS ?=

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

.PHONY: all build-image run-whatrecord run-test inspect
