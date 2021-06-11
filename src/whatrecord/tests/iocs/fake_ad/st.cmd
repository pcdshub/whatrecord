epicsEnvSet("QSIZE", 100)
epicsEnvSet("PORT", "PORT")
epicsEnvSet("PREFIX", "AD:")

# Implicitly create PVA group "AD:Pva1:Image"
NDPvaConfigure("PVA1", $(QSIZE), 0, "$(PORT)", 0, $(PREFIX)Pva1:Image, 0, 0, 0)
