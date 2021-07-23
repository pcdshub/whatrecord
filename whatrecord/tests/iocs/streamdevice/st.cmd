dbLoadDatabase "../v3_softIoc.dbd"
streamApp_registerRecordDeviceDriver

epicsEnvSet "STREAM_PROTOCOL_PATH", "."

drvAsynIPPortConfigure "terminal", "localhost:40000"

dbLoadRecords "test.db","P=STREAM"

#log debug output to file
#streamSetLogfile StreamDebug.log

iocInit

var streamDebug 1
