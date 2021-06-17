===============================
whatrecord
===============================

.. image:: https://img.shields.io/travis/pcdshub/whatrecord.svg
        :target: https://travis-ci.org/pcdshub/whatrecord

.. image:: https://img.shields.io/pypi/v/whatrecord.svg
        :target: https://pypi.python.org/pypi/whatrecord


EPICS IOC record search and meta information tool.

Spiritual successor of recordwhat.

What?
-----

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

Hopefully it'll get released before I get tired of it.

Record?
-------

https://docs.epics-controls.org/en/latest/guides/EPICS_Process_Database_Concepts.html#the-epics-process-database

Documentation
-------------

https://pcdshub.github.io/whatrecord/

Not yet. But I'm thinking of trying mkdocs for fun.

Requirements
------------

* Python 3.7+
* aiohttp
* apischema[graphql]
* cython
* epicscorelibs
* graphviz
* jinja2
* lark
