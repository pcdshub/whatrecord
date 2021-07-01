#!/usr/bin/env softIoc

epicsEnvSet( "ENGINEER", "Engineer" )
epicsEnvSet( "LOCATION", "Location" )
epicsEnvSet( "IOCSH_PS1", "ioc-tst-pva-misc> " )
epicsEnvSet( "EPICS_BASE", "/cds/group/pcds/epics/base/R7.0.2" )

dbLoadDatabase("../softIoc.dbd", 0, 0)

softIoc_registerRecordDeviceDriver(pdbbase)

dbLoadRecords("../db/pva/basic.db", "N=IOC:PVA:MISC:")
dbLoadRecords("../db/pva/circle.db", "PREFIX=IOC:PVA:MISC:CIRCLE:")
dbLoadRecords("../db/pva/image.db", "PREFIX=IOC:PVA:MISC:IMAGE:")
dbLoadRecords("../db/pva/iq.db", "PREFIX=IOC:PVA:MISC:IQ:")
dbLoadRecords("../db/pva/pva.db", "PREFIX=IOC:PVA:MISC:PVADOCS:")
dbLoadRecords("../db/pva/table.db", "N=IOC:PVA:MISC:TABLE:")

iocInit

dbl
