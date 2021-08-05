#!/usr/bin/env softIoc

epicsEnvSet( "ENGINEER", "Engineer" )
epicsEnvSet( "LOCATION", "Location" )
epicsEnvSet( "IOCSH_PS1", "ioc-dbloadtemplate> " )
epicsEnvSet( "EPICS_BASE", "/cds/group/pcds/epics/base/R7.0.2" )

dbLoadDatabase("../softIoc.dbd", 0, 0)

softIoc_registerRecordDeviceDriver(pdbbase)

dbLoadTemplate "../db/test.substitutions"

iocInit

dbl
