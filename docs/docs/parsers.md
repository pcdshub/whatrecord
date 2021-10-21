# Parsers

## Usage

For each of the parser classes:

* [AccessSecurityConfig](#whatrecord.access_security.AccessSecurityConfig)
* [Database](#whatrecord.db.Database)
* [GatewayPVList](#whatrecord.gateway.PVList)
* [LclsEpicsArchFile](#whatrecord.plugins.epicsarch.LclsEpicsArchFile)
* [SequencerProgram](#whatrecord.snl.SequencerProgram)
* [StreamProtocol](#whatrecord.streamdevice.StreamProtocol)
* [TemplateSubstitution](#whatrecord.dbtemplate.TemplateSubstitution)

Data can be loaded from a file, file object, or string. Filename information
will be automatically added to the load context information when available,
but may be specified separately in the latter case.

Taking [AccessSecurityConfig](#whatrecord.access_security.AccessSecurityConfig)
for example:

```python
from whatrecord import AccessSecurityConfig

# 1. Load from a file directly
config = AccessSecurityConfig.from_file("filename.acf")

# 2. Load from a file object
with open("filename.acf", "rt") as fp:
    config = AccessSecurityConfig.from_file_obj(fp)

# 3. Load from a string:
with open("filename.acf", "rt") as fp:
    contents = fp.read()

config = AccessSecurityConfig.from_string(contents, filename="filename.acf")
```

## API

::: whatrecord.access_security
::: whatrecord.autosave
::: whatrecord.db
::: whatrecord.dbtemplate
::: whatrecord.gateway
::: whatrecord.snl
::: whatrecord.streamdevice
::: whatrecord.transformer
