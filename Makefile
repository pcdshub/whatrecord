all: install server

IPY_OPTS ?= -i
GATEWAY_CONFIG ?= /reg/g/pcds/gateway/config/
STARTUP_SCRIPTS ?= $(shell cat all_stcmds.txt)
PORT ?= 8899

MACOSX_DEPLOYMENT_TARGET ?= 10.9

install:
	MACOSX_DEPLOYMENT_TARGET=$(MACOSX_DEPLOYMENT_TARGET) pip install  .

ipython:
	ipython -i -c "import sys, whatrecord.shell; from whatrecord.shell import whatrec; from whatrecord.graph import graph_links; cnt = whatrecord.shell.load_startup_scripts(*sys.argv[4:])" $(STARTUP_SCRIPTS)

time:
	time python -c "import sys, whatrecord.shell; from whatrecord.shell import whatrec; cnt = whatrecord.shell.load_startup_scripts(*sys.argv[1:])" $(STARTUP_SCRIPTS)

profile:
	sudo py-spy record -o profile.speedscope -f speedscope -- python -c "import sys, whatrecord.shell; from whatrecord.shell import whatrec; cnt = whatrecord.shell.load_startup_scripts(*sys.argv[1:])" $(STARTUP_SCRIPTS)

server:
	ipython -i `which whatrec` -- server \
		--archive-file all_archived_pvs.json \
		--gateway-config $(GATEWAY_CONFIG) \
		--scripts $(STARTUP_SCRIPTS) \
		--port $(PORT) \
		$(SERVER_ARGS)

.phony: install ipython server profile time
