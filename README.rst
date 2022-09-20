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

Makefile / build system information

* Determine build dependencies from a ``Makefile``
* Recursively inspect sub-dependencies
* Graph IOC dependency information or output it as JSON

Command-line tools

* ``whatrecord lint`` - lint a database
* ``whatrecord parse`` - parse supported formats
* ``whatrecord server`` - start the API server
* ``whatrecord graph`` - graph PV relationships, SNL diagrams, IOC dependencies

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

Docker
------

See `/docker </docker>`_ to set up a Python 3.10-based whatrecord container.
A docker-compose configuration for starting up the frontend/backend servers
is also provided.  Note that the default configuration only indexes the
whatrecord-provided IOCs.

Frontend Screenshots
--------------------

Search for records and view relationships:

.. image:: https://github.com/pcdshub/whatrecord/raw/assets/screenshot_1.png

View StreamDevice protocol information:

.. image:: https://github.com/pcdshub/whatrecord/raw/assets/screenshot_2.png

See where your qsrv pvAccess keys come from:

.. image:: https://github.com/pcdshub/whatrecord/raw/assets/screenshot_3.png

See access security settings:

.. image:: https://github.com/pcdshub/whatrecord/raw/assets/screenshot_4.png

View all of your IOCs in one place and browse their records by type:

.. image:: https://github.com/pcdshub/whatrecord/raw/assets/screenshot_5.png

View inter-IOC record relationships:

.. image:: https://github.com/pcdshub/whatrecord/raw/assets/screenshot_6.png

View all of your ophyd/happi devices and their relevant PVs:

.. image:: https://github.com/pcdshub/whatrecord/raw/assets/screenshot_7.png

View LDAP-provided settings:

.. image:: https://github.com/pcdshub/whatrecord/raw/assets/screenshot_8.png

(LCLS-specific) View epicsArch DAQ PVs:

.. image:: https://github.com/pcdshub/whatrecord/raw/assets/screenshot_9.png

View gateway PVList configurations:

.. image:: https://github.com/pcdshub/whatrecord/raw/assets/screenshot_10.png

View record duplicates:

.. image:: https://github.com/pcdshub/whatrecord/raw/assets/screenshot_11.png

View API server logs:

.. image:: https://github.com/pcdshub/whatrecord/raw/assets/screenshot_12.png

See per-parameter values:

.. image:: https://github.com/pcdshub/whatrecord/raw/assets/screenshot_13.png
.. image:: https://github.com/pcdshub/whatrecord/raw/assets/screenshot_15.png

See database lint:

.. image:: https://github.com/pcdshub/whatrecord/raw/assets/screenshot_14.png


Other Screenshots
-----------------

Use ``whatrecord deps --graph`` to inspect IOCs/modules with ``make`` and
generate a dependency graph of modules:

.. image:: https://github.com/pcdshub/whatrecord/raw/assets/screenshot_16.png

Use ``whatrecord graph`` to graph state notation language ``.st`` file
logic:

.. image:: https://github.com/pcdshub/whatrecord/raw/assets/screenshot_17.png

.. image:: https://github.com/pcdshub/whatrecord/raw/assets/screenshot_18.png
