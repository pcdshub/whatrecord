#!/usr/bin/env softIoc

epicsEnvSet( "ENGINEER", "Engineer" )
epicsEnvSet( "LOCATION", "Location" )
epicsEnvSet( "IOCSH_PS1", "ioc-tst-autosave> " )
epicsEnvSet( "EPICS_BASE", "/cds/group/pcds/epics/base/R7.0.2" )

dbLoadDatabase("../softIoc.dbd", 0, 0)

softIoc_registerRecordDeviceDriver(pdbbase)

### save_restore setup
# status-PV prefix
save_restoreSet_status_prefix("as:")
# Debug-output level
save_restoreSet_Debug(0)

# Ok to save/restore save sets with missing values (no CA connection to PV)?
save_restoreSet_IncompleteSetsOk(1)
# Save dated backup files?
save_restoreSet_DatedBackupFiles(1)

# Number of sequenced backup files to write
save_restoreSet_NumSeqFiles(3)
# Time interval between sequenced backups
save_restoreSet_SeqPeriodInSeconds(300)

# If you want save_restore to manage its own NFS mount, specify the name and
# IP address of the file server to which save files should be written.
# This currently is supported only on vxWorks.
# NOTE: whatrecord does not yet support vxworks/rtems/cexpsh stuff
# save_restoreSet_NFSHost("oxygen", "164.54.52.4")

# specify where save files should be
set_savefile_path("", "autosave")

# specify what save files should be restored.  Note these files must be
# in the directory specified in set_savefile_path(), or, if that function
# has not been called, from the directory current when iocInit is invoked

# Save files associated with the request files 'auto_positions.req' and
# 'auto_settings.req'.  These files are the standard way to use autosave in
# synApps.
set_pass0_restoreFile("auto_positions.sav")
set_pass0_restoreFile("auto_settings.sav")
set_pass1_restoreFile("auto_settings.sav")

# Save files associated with the request files 'info_positions.req' and
# 'info_settings.req'.  These .req files are written by the autosave function
# makeAutosaveFiles().
set_pass0_restoreFile("info_positions.sav")
set_pass0_restoreFile("info_settings.sav")
set_pass1_restoreFile("info_settings.sav")

# specify directories in which to to search for included request files
set_requestfile_path("", "")
set_requestfile_path("", "autosave")
:: set_requestfile_path(autosave, "asApp/Db")

dbLoadRecords("../db/save_restoreStatus.db", "P=IOC:autosave:as:")

# daily periodic dated backups (period is specified in minutes)
save_restoreSet_periodicDatedBackups(1440)

dbLoadRecords("../db/basic_asyn_motor.db", "P=IOC:autosave:,M=sample_positioner")
dbLoadRecords("../db/configMenu.db", "P=IOC:autosave:,CONFIG=scan1")

iocInit

### Start up the autosave task and tell it what to do.
# The task is actually named "save_restore".
# (See also, 'initHooks' above, which is the means by which the values that
# will be saved by the task we're starting here are going to be restored.
# Note that you can reload these sets after creating them: e.g.,
# reload_monitor_set("auto_settings.req",30,"P=as:")
#
# save positions every five seconds
create_monitor_set("auto_positions.req",5,"P=IOC:autosave:as:")
# save other things every thirty seconds
create_monitor_set("auto_settings.req",30,"P=IOC:autosave:as:")

# The following command makes the autosave request files 'info_settings.req',
# and 'info_positions.req', from information (info nodes) contained in all of
# the EPICS databases that have been loaded into this IOC.
makeAutosaveFiles()
create_monitor_set("info_positions.req",5,"P=IOC:autosave:as:")
create_monitor_set("info_settings.req",30,"P=IOC:autosave:as:")

# configMenu example
# Note that the request file MUST be named $(CONFIG)Menu.req
# If the macro CONFIGMENU is defined with any value, backup (".savB") and
# sequence files (".savN") will not be written.  We don't want these for
# configMenu.
create_manual_set("scan1Menu.req","P=IOC:autosave:,CONFIG=scan1,CONFIGMENU=1")
