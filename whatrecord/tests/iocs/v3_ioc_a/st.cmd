#!/usr/bin/env softIoc

epicsEnvSet( "ENGINEER", "Engineer" )
epicsEnvSet( "LOCATION", "Location" )
epicsEnvSet( "IOCSH_PS1", "ioc-tst-v3-a> " )

dbLoadDatabase("../v3_softIoc.dbd", 0, 0)

softIoc_registerRecordDeviceDriver(pdbbase)


dbLoadRecords("ioc_a.db", "P=IOC:KFE:V3:A")

iocInit

dbl
