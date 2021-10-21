===============================
whatrecord
===============================

.. image:: https://img.shields.io/travis/pcdshub/whatrecord.svg
        :target: https://travis-ci.org/pcdshub/whatrecord

.. image:: https://img.shields.io/pypi/v/whatrecord.svg
        :target: https://pypi.python.org/pypi/whatrecord


EPICS IOC record search and meta information tool.

Spiritual successor of recordwhat.

https://pcdshub.github.io/whatrecord/

What?
-----

Lark grammar-based parsers which parse any of the following into easy-to-use
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

Pseudo-IOC shell interpreter:
* Reads st.cmd files as if it were an IOC
* Loads and lints record files (and other supported formats above)
* Builds inter- and intra- IOC PV relationship graphs
* Stores context information about where each record/field/etc came from

API server
* IOC finder (LCLS IOC manager, list of files, or external script)
* Provides access to all parsed information above
* Preliminary asyncio-based client to talk with the server

Frontend
* User-friendly vue.js v3 frontend that communicates with API server
* Interfaces for:
    - Searching for records
    - Record relationships (processing and links, cross-IOC links)
    - IOC information
    - Gateway configuration overview
    - Duplicate records
    - Optional plugins

Plugins
* happi devices
* Simple LDAP search (LCLS hosts, "netconfig")
* LCLS-specific epicsArch / logbook DAQ PVs
* TwinCAT PLC source code (pytmc)

Command-line tools
* ``whatrecord lint`` - lint a database
* ``whatrecord parse`` - parse supported formats
* ``whatrecord server`` - start the API server

Record?
-------

https://docs.epics-controls.org/en/latest/guides/EPICS_Process_Database_Concepts.html#the-epics-process-database

Requirements
------------

Requirements:
* Python 3.9
* aiohttp
* apischema[graphql]
* graphviz
* jinja2
* lark

Build requirements:
* cython
* epicscorelibs
