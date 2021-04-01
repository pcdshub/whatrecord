all: install server

IPY_OPTS ?= -i
GATEWAY_CONFIG ?= /Users/klauer/Repos/gateway-setup/config
STARTUP_SCRIPTS ?= \
	/Users/klauer/Repos/iocs/reg/g/pcds/epics/ioc/las/ims/R0.3.1/iocBoot/ioc-las-cxi-phase-ims/st.cmd \
	/Users/klauer/Repos/lcls-plc-kfe-motion/iocBoot/ioc-kfe-motion/st.cmd \
	/Users/klauer/Repos/iocs/reg/g/pcds/epics/ioc/las/vitara/R2.12.1/iocBoot/ioc-las-cxi-vitara/st.cmd

install:
	pip install  .

ipython:
	ipython -i -c "import sys, whatrecord.shell; from whatrecord.shell import whatrec; from whatrecord.graph import graph_links; cnt = whatrecord.shell.load_multiple_startup_scripts(*sys.argv[4:])" $(STARTUP_SCRIPTS)

server:
	ipython -i `which whatrec` -- server \
		--archive-file all_archived_pvs.json \
		--gateway-config $(GATEWAY_CONFIG) \
		--scripts $(STARTUP_SCRIPTS)

.phony: install ipython server
