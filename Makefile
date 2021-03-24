all: install run

IPY_OPTS ?= -i
STARTUP_SCRIPT ?= /Users/klauer/Repos/iocs/reg/g/pcds/epics/ioc/las/ims/R0.3.1/iocBoot/ioc-las-cxi-phase-ims/st.cmd
# /Users/klauer/Repos/lcls-plc-kfe-motion/iocBoot/ioc-kfe-motion/st.cmd
# /Users/klauer/Repos/iocs/reg/g/pcds/epics/ioc/las/vitara/R2.12.1/iocBoot/ioc-las-cxi-vitara/st.cmd

install:
	pip install  .

run:
	ipython -i -c "import whatrecord.shell; sh = whatrecord.shell.simple_test('$(STARTUP_SCRIPT)')"

.phony: install run ipython
