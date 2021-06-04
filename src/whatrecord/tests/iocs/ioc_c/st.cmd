#!/usr/bin/env softIoc

epicsEnvSet( "ENGINEER", "Engineer" )
epicsEnvSet( "LOCATION", "Location" )
epicsEnvSet( "IOCSH_PS1", "ioc-tst-c> " )
epicsEnvSet( "PREFIX", "IOC:KFE:C" )

dbLoadDatabase("../softIoc.dbd", 0, 0)

softIoc_registerRecordDeviceDriver(pdbbase)

dbLoadRecords("ioc.db", "P=$(PREFIX)")

iocInit

dbl
