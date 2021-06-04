#!/usr/bin/env softIoc

epicsEnvSet( "ENGINEER", "Engineer" )
epicsEnvSet( "LOCATION", "Location" )
epicsEnvSet( "IOCSH_PS1", "ioc-tst-a> " )

dbLoadDatabase("../softIoc.dbd", 0, 0)

softIoc_registerRecordDeviceDriver(pdbbase)


dbLoadRecords("ioc_a.db", "P=IOC:KFE:A")

iocInit

dbl
