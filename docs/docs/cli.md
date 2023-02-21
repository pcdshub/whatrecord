# CLI

Top-level options:

```
usage: whatrecord [-h] [--version] [--log LOG_LEVEL]
                  {info,iocmanager-loader,lint,parse,server} ...

`whatrecord` is the top-level command for accessing various subcommands.

Try::

    $ whatrecord info --help
    $ whatrecord iocmanager-loader --help
    $ whatrecord lint --help
    $ whatrecord parse --help
    $ whatrecord server --help

positional arguments:
  {info,iocmanager-loader,lint,parse,server}
                        Possible subcommands

optional arguments:
  -h, --help            show this help message and exit
  --version, -V         Show the whatrec version number and exit.
  --log LOG_LEVEL, -l LOG_LEVEL
                        Python logging level (e.g. DEBUG, INFO, WARNING)
```

## lint

``whatrecord lint`` is used to lint a startup script or database file. See
if there are errors in your database file, startup script contents, etc.

```
usage: whatrecord lint [-h] [--dbd DBD] [--standin-directory [STANDIN_DIRECTORY ...]] [--json] [-v] [--use-gdb] filename

"whatrecord lint" is used to lint a startup script or database file.

positional arguments:
  filename              Startup script filename

optional arguments:
  -h, --help            show this help message and exit
  --dbd DBD             The dbd file, if parsing a database
  --standin-directory [STANDIN_DIRECTORY ...]
                        Map a "stand-in" directory to another on disk
  --json
  -v, --verbose         Increase verbosity
  --use-gdb             Use metadata derived from the script binary
```

## parse

"whatrecord parse" is used to parse and interpret any of whatrecord's supported
file formats, dumping the results to the console (standard output) in JSON
format, by default.

```
usage: whatrecord parse [-h] [--format FORMAT] [--dbd DBD]
                        [--standin-directory [STANDIN_DIRECTORY ...]] [--macros MACROS]
                        [--friendly] [--friendly-format FRIENDLY_FORMAT] [--use-gdb] [--expand]
                        filename

"whatrecord parse" is used to parse and interpret any of whatrecord's supported
file formats, dumping the results to the console (standard output) in JSON
format, by default.

positional arguments:
  filename              Startup script filename

optional arguments:
  -h, --help            show this help message and exit
  --format FORMAT       The file format.  For files that lack a recognized
                        extension or are otherwise misidentified by whatrecord.
  --dbd DBD             The dbd file, if parsing a database
  --standin-directory [STANDIN_DIRECTORY ...]
                        Map a "stand-in" directory to another on disk
  --macros MACROS       Macro to add, in the usual form ``macro=value,...``
  --friendly            Output Python object representation instead of JSON
  --friendly-format FRIENDLY_FORMAT
                        Output Python object representation instead of JSON
  --use-gdb             Use metadata derived from the script binary
  --expand              Expand a substitutions file, as in the msi tool
```

## server

This is how to start the API server.

```
usage: whatrecord server [-h] [--scripts [SCRIPTS ...]] [--script-loader [SCRIPT_LOADER ...]]
                         [--archive-management-url ARCHIVE_MANAGEMENT_URL]
                         [--gateway-config GATEWAY_CONFIG]
                         [--standin-directory [STANDIN_DIRECTORY ...]] [--port PORT]
                         [--tracemalloc]

"whatrecord server" is used to start an aiohttp-backed web server which hosts
startup script and record information.

optional arguments:
  -h, --help            show this help message and exit
  --scripts [SCRIPTS ...]
                        Startup script filename(s)
  --script-loader [SCRIPT_LOADER ...]
                        Run an external script to get IOC configuration information
  --archive-management-url ARCHIVE_MANAGEMENT_URL
                        Archiver management URL for finding archived PVs.
  --gateway-config GATEWAY_CONFIG
                        Gateway configuration file or directory
  --standin-directory [STANDIN_DIRECTORY ...]
                        Map a "stand-in" directory to another on disk
  --port PORT           Web server TCP port
  --tracemalloc         [Debug] Use tracemalloc to debug server memory usage
```

## info

``whatrecord info`` talks to the API server to get information about a record.

```
usage: whatrecord info [-h] [--json] records [records ...]

"whatrecord info" is used to get PV information from the whatrecord server.

positional arguments:
  records     Record name(s)

optional arguments:
  -h, --help  show this help message and exit
  --json      Output raw JSON
```

## API

::: whatrecord.bin
::: whatrecord.bin.main
::: whatrecord.bin.lint
::: whatrecord.bin.parse
::: whatrecord.bin.server
