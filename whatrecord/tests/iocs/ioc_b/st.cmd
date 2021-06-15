#!/usr/bin/env softIoc

epicsEnvSet( "ENGINEER", "Engineer" )
epicsEnvSet( "LOCATION", "Location" )
epicsEnvSet( "IOCSH_PS1", "ioc-tst-b> " )

dbLoadDatabase("../softIoc.dbd", 0, 0)

softIoc_registerRecordDeviceDriver(pdbbase)


dbLoadRecords("ioc_b.db", "P=IOC:KFE:B")

iocInit

dbl
