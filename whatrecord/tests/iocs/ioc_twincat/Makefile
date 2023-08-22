IOC_TOP = /reg/g/pcds/epics/ioc/common/ads-ioc/R0.6.1
IOC_INSTANCE_PATH := $(shell pwd)

# Set PRODUCTION_IOC to 1 to move from a testing to a production IOC:
PRODUCTION_IOC := 1

PROJECT_NAME = project_c
PROJECT_PATH := ../../blark_root/project_c/project_c/project_c.tsproj
PLC = ProjectC

PYTMC_OPTS :=
PREFIX = PROJECT:C

include $(IOC_TOP)/iocBoot/templates/Makefile.base
