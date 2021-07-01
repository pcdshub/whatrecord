epicsEnvSet("QSIZE", 100)
epicsEnvSet("PORT", "PORT")
epicsEnvSet("PREFIX", "AD:")
epicsEnvSet( "EPICS_BASE", "/cds/group/pcds/epics/base/R7.0.2" )

# Implicitly create PVA group "AD:Pva1:Image"
NDPvaConfigure("PVA1", $(QSIZE), 0, "$(PORT)", 0, $(PREFIX)Pva1:Image, 0, 0, 0)
