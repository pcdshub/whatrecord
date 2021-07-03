#!/usr/bin/env softIoc

epicsEnvSet( "ENGINEER", "Engineer" )
epicsEnvSet( "LOCATION", "Location" )
epicsEnvSet( "IOCSH_PS1", "ioc-tst-c> " )
epicsEnvSet( "PREFIX", "IOC:KFE:C" )
epicsEnvSet( "EPICS_BASE", "/cds/group/pcds/epics/base/R7.0.2" )
epicsEnvSet( "EPICS_DB_INCLUDE_PATH", "$(PWD)/../:$(PWD)" )

cd /

dbLoadDatabase("softIoc.dbd", 0, 0)

softIoc_registerRecordDeviceDriver(pdbbase)

dbLoadRecords("ioc.db", "P=$(PREFIX)")

iocInit

dbl
