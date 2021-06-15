#!/usr/bin/env softIoc

epicsEnvSet( "ENGINEER", "Engineer" )
epicsEnvSet( "LOCATION", "Location" )
epicsEnvSet( "IOCSH_PS1", "ioc-tst-pva-simple> " )

dbLoadDatabase("../softIoc.dbd", 0, 0)

softIoc_registerRecordDeviceDriver(pdbbase)


dbLoadRecords("ioc_pva_simple.db", "PREFIX=IOC:PVA:SIMPLE:")

iocInit

dbl
