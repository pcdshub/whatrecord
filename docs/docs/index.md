# whatrecord

## What is this?

whatrecord provides a variety of independent tools that work together as part
of a larger web-facing application for gathering information about EPICS IOCs
and related files.

### Lark grammar-based parsers

Lark-based grammars allow for parsing any of the following into easy-to-use
Python dataclasses:

* EPICS access security files (.acf)
* EPICS autosave save files (.sav)
* EPICS V3 database files
* EPICS V4 database files
* EPICS msi-style template/substitutions files (.template/.substitutions)
* EPICS gateway configuration (.pvlist)
* EPICS sequencer state notation language programs (.st)
* EPICS StreamDevice protocols (.proto)

All of the above can be easily serialized to JSON for interoperability.

### Pseudo-IOC shell interpreter

* Reads st.cmd files as if whatrecord were the IOC process
* Loads and lints record files (and other supported formats above)
* Builds inter- and intra- IOC PV relationship graphs
* Stores context information about where each record/field/etc came from

### API server

* IOC finder (LCLS IOC manager, list of files, or external script)
* Provides access to all parsed information above
* Preliminary asyncio-based client to talk with the server

### Frontend

This is a user-friendly vue.js v3 frontend that communicates with API server.

It contains interfaces for:

* Searching for records
* Record relationships (processing and links, cross-IOC links)
* IOC information
* Gateway configuration overview
* Duplicate records
* Optional plugins
* API server logs

### Plugins

* happi devices
* Simple LDAP search (LCLS hosts, "netconfig")
* LCLS-specific epicsArch / logbook DAQ PVs
* TwinCAT PLC source code (pytmc)

### Makefile / build system information

* Determine build dependencies from a ``Makefile``
* Recursively inspect sub-dependencies
* Graph IOC dependency information or output it as JSON

### Command-line tools

* ``whatrecord lint`` - lint a database
* ``whatrecord parse`` - parse supported formats to JSON
* ``whatrecord server`` - start the API server
* ``whatrecord graph`` - graph PV relationships, SNL diagrams, IOC dependencies
* Plugins can similarly be executed to provide parsed information in JSON

## Installing

```bash
$ pip install whatrecord
```

## Starting the server

See [Server / client](server_client.md) for more information.

## Fair warning

* whatrecord isn’t error or bug-free
* whatrecord aims to be as compliant as possible when parsing the formats it
  supports, but there may be discrepancies.
    - If you find a case where it parses something incorrectly (or doesn't parse
      it at all) please create an issue.
* whatrecord isn’t a good example of how to store relational data.  The initial
  goals were breadth-first feature support:
    - Parse and interpret everything: in-memory dataclasses storing all
      information
    - Get it to be displayed in a friendly way
    - _Efficient storage can be tackled later!_
* Database-backed information along with and corresponding backend/frontend
  changes will need to be pursued

## Background

This started out as a project where I thought I'd reuse as much of epics-base
as possible to generate information about IOCs for easy indexing, and all the
while learn about some modern web development practices.

In no particular order, the project has gone through some transformations:

I ended up writing a bunch of Lark grammars which effectively replaced
the need for epics-pypdb and other miscellaneous core stuff in epics-base.

the possibilities for such a tool became more clear to me, specifically
targetting EPICS IOC record debugging.

I was curious if we were using pva2pva at all. So now the grammars
will load up pvAccess Q:group tags.  But it's likely not 100% correct, and
certainly not complete.

I had other thoughts about what could be integrated (gateway, happi, pytmc,
IOC dependencies, versions, ...)

It's likely this hasn't finished morphing just yet.  I definitely need to
circle back and clean up the initial prototype mess.
