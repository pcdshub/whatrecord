from __future__ import annotations

import asyncio
import functools
import inspect
import json
import logging
import os
import pathlib
import signal
import sys
import traceback
from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass, field
from typing import (Callable, Dict, Generator, Iterable, List, Optional, Tuple,
                    Union)

import apischema

from . import asyn, graph
from . import motor as motor_mod
from . import settings, streamdevice, util
from .access_security import AccessSecurityConfig
from .common import (FullLoadContext, IocMetadata, IocshCmdArgs, IocshRedirect,
                     IocshResult, IocshScript, LoadContext, MutableLoadContext,
                     PVRelations, RecordDefinitionAndInstance, RecordInstance,
                     WhatRecord, time_context)
from .db import Database, DatabaseLoadFailure, LinterResults, RecordType
from .format import FormatContext
from .iocsh import parse_iocsh_line, split_words
from .macro import MacroContext

logger = logging.getLogger(__name__)


@dataclass
class ShellState:
    """
    IOC shell state container.

    Contains hooks for commands and state information.

    Parameters
    ----------
    prompt : str, optional
        The prompt - PS1 - as in "epics>".
    string_encoding : str, optional
        String encoding for byte strings and files.
    variables : dict, optional
        Starting state for variables (not environment variables).

    Attributes
    ----------
    prompt : str
        The prompt - PS1 - as in "epics>".
    variables : dict
        Shell variables.
    string_encoding : str
        String encoding for byte strings and files.
    macro_context : MacroContext
        Macro context for commands that are evaluated.
    standin_directories : dict
        Rewrite hard-coded directory prefixes by setting::

            standin_directories = {"/replace_this/": "/with/this"}
    working_directory : pathlib.Path
        Current working directory.
    database_definition : Database
        Loaded database definition (dbd).
    database : Dict[str, RecordInstance]
        The IOC database of records.
    aliases : Dict[str, str]
        Alias name to record name.
    load_context : List[MutableLoadContext]
        Current loading context stack (e.g., ``st.cmd`` then
        ``common_startup.cmd``).  Modified in place as scripts are evaluated.
    """

    prompt: str = "epics>"
    variables: Dict[str, str] = field(default_factory=dict)
    string_encoding: str = "latin-1"
    ioc_initialized: bool = False
    standin_directories: Dict[str, str] = field(default_factory=dict)
    working_directory: pathlib.Path = field(
        default_factory=lambda: pathlib.Path.cwd(),
    )
    aliases: Dict[str, str] = field(default_factory=dict)
    database_definition: Optional[Database] = None
    database: Dict[str, RecordInstance] = field(default_factory=dict)
    access_security: Optional[AccessSecurityConfig] = None
    access_security_filename: Optional[pathlib.Path] = None
    access_security_macros: Optional[Dict[str, str]] = None
    pva_database: Dict[str, RecordInstance] = field(default_factory=dict)
    load_context: List[MutableLoadContext] = field(default_factory=list)
    asyn_ports: Dict[str, asyn.AsynPortBase] = field(default_factory=dict)
    loaded_files: Dict[str, str] = field(
        default_factory=dict,
    )
    macro_context: MacroContext = field(
        default_factory=MacroContext, metadata=apischema.metadata.skip
    )
    ioc_info: IocMetadata = field(default_factory=IocMetadata)
    db_add_paths: List[pathlib.Path] = field(default_factory=list)
    streamdevice: Dict[str, streamdevice.StreamProtocol] = field(
        default_factory=dict
    )

    _handlers: Dict[str, Callable] = field(
        default_factory=dict, metadata=apischema.metadata.skip
    )

    def __post_init__(self):
        self._handlers.update(dict(self.find_handlers()))
        self._setup_dynamic_handlers()
        self.macro_context.string_encoding = self.string_encoding

    def _setup_dynamic_handlers(self):
        # Just motors for now
        for name, args in motor_mod.shell_commands.items():
            if name not in self._handlers:
                self._handlers[name] = functools.partial(
                    self._generic_motor_handler, name
                )

    def find_handlers(self):
        for attr, obj in inspect.getmembers(self):
            if attr.startswith("handle_") and callable(obj):
                name = attr.split("_", 1)[1]
                yield name, obj

    def load_file(self, filename: Union[pathlib.Path, str]) -> Tuple[pathlib.Path, str]:
        """Load a file, record its hash, and return its contents."""
        filename = self._fix_path(filename)
        filename = filename.resolve()
        shasum, contents = util.read_text_file_with_hash(
            filename, encoding=self.string_encoding
        )
        self.loaded_files[str(filename)] = shasum
        self.ioc_info.loaded_files[str(filename)] = shasum
        return filename, contents

    def _handle_input_redirect(
        self,
        redir: IocshRedirect,
        shresult: IocshResult,
        recurse: bool = True,
        raise_on_error: bool = False,
    ):
        try:
            filename, contents = self.load_file(redir.name)
        except Exception as ex:
            shresult.error = f"{type(ex).__name__}: {redir.name}"
            yield shresult
            return

        yield shresult
        yield from self.interpret_shell_script_text(
            contents.splitlines(), recurse=recurse, name=filename
        )

    def interpret_shell_line(self, line, recurse=True, raise_on_error=False):
        """Interpret a single shell script line."""
        shresult = parse_iocsh_line(
            line,
            context=self.get_load_context(),
            prompt=self.prompt,
            macro_context=self.macro_context,
            string_encoding=self.string_encoding,
        )
        input_redirects = [redir for redir in shresult.redirects if redir.mode == "r"]
        if shresult.error:
            yield shresult
        elif input_redirects:
            if recurse:
                yield from self._handle_input_redirect(
                    input_redirects[0],
                    shresult,
                    recurse=recurse,
                    raise_on_error=raise_on_error,
                )
        elif shresult.argv:
            try:
                result = self.handle_command(*shresult.argv)
                if result:
                    # Only set if not-None to speed up serialization
                    shresult.result = result
            except Exception as ex:
                if raise_on_error:
                    raise
                ex_details = traceback.format_exc()
                shresult.error = f"Failed to execute: {ex}:\n{ex_details}"

            yield shresult
            if isinstance(shresult.result, IocshCmdArgs):
                yield from self.interpret_shell_line(
                    shresult.result.command, recurse=recurse
                )
        else:
            # Otherwise, nothing to do
            yield shresult

    def interpret_shell_script(
        self,
        filename: Union[pathlib.Path, str],
        recurse: bool = True,
        raise_on_error: bool = False,
    ) -> Generator[IocshResult, None, None]:
        """Load and interpret a shell script named ``filename``."""
        filename, contents = self.load_file(filename)
        yield from self.interpret_shell_script_text(
            contents.splitlines(),
            name=str(filename),
            recurse=recurse,
            raise_on_error=raise_on_error,
        )

    def interpret_shell_script_text(
        self,
        lines: Iterable[str],
        name: str = "unknown",
        recurse: bool = True,
        raise_on_error: bool = False,
    ) -> Generator[IocshResult, None, None]:
        """Interpret a shell script named ``name`` with ``lines`` of text."""
        load_ctx = MutableLoadContext(str(name), 0)
        try:
            self.load_context.append(load_ctx)
            for lineno, line in enumerate(lines, 1):
                load_ctx.line = lineno
                yield from self.interpret_shell_line(
                    line,
                    recurse=recurse,
                    raise_on_error=raise_on_error,
                )
        finally:
            self.load_context.remove(load_ctx)

    def get_asyn_port_from_record(self, inst: RecordInstance) -> Optional[asyn.AsynPort]:
        """Given a record, return its related asyn port."""
        rec_field = inst.fields.get("INP", inst.fields.get("OUT", None))
        if rec_field is None:
            return

        if not isinstance(rec_field.value, str):
            # No PVAccess links just yet
            return

        value = rec_field.value.strip()
        if value.startswith("@asyn"):
            try:
                asyn_args = value.split("@asyn")[1].strip(" ()")
                asyn_port, *_ = asyn_args.split(",")
                return self.asyn_ports.get(asyn_port.strip(), None)
            except Exception:
                logger.debug("Failed to parse asyn string", exc_info=True)

    def get_load_context(self) -> FullLoadContext:
        """Get a FullLoadContext tuple representing where we are now."""
        if not self.load_context:
            return tuple()
        return tuple(ctx.to_load_context() for ctx in self.load_context)

    def handle_command(self, command, *args):
        handler = self._handlers.get(command, None)
        if handler is not None:
            return handler(*args)
        return self.unhandled(command, args)

    def _fix_path(self, filename: Union[str, pathlib.Path]):
        filename = str(filename)
        if os.path.isabs(filename):
            for from_, to in self.standin_directories.items():
                if filename.startswith(from_):
                    _, suffix = filename.split(from_, 1)
                    return pathlib.Path(to + suffix)

        return self.working_directory / filename

    @property
    def db_include_paths(self) -> List[pathlib.Path]:
        """Database include paths (EPICS_DB_INCLUDE_PATH)."""
        env_paths = self.paths_from_env_var("EPICS_DB_INCLUDE_PATH")
        if not env_paths:
            return [self.working_directory] + self.db_add_paths
        return env_paths + self.db_add_paths

    def paths_from_env_var(
        self,
        env_var: str,
        *,
        default: Optional[str] = None
    ) -> List[pathlib.Path]:
        """Paths from an environment variable (or macro)."""
        env_var = self.macro_context.get(env_var, default) or ""
        return [
            (self.working_directory / pathlib.Path(path)).resolve()
            # TODO: this is actually OS-dependent (: on linux, ; on Windows)
            for path in env_var.split(":")
        ]

    def _fix_path_with_search_list(
        self,
        filename: Union[str, pathlib.Path],
        include_paths: List[pathlib.Path],
    ) -> pathlib.Path:
        """Given a list of paths, find ``filename``."""
        filename = str(filename)
        if not include_paths or "/" in filename or "\\" in filename:
            # Inclue path unset or even something resembling a nested path
            # automatically is used as-is
            return self.working_directory / filename

        for path in include_paths:
            option = path / filename
            if option.exists() and option.is_file():
                return option

        paths = list(str(path) for path in include_paths)
        raise FileNotFoundError(
            f"File {filename!r} not found in search path: {paths}"
        )

    def unhandled(self, command, args):
        ...
        # return f"No handler for handle_{command}"

    def _generic_motor_handler(self, name, *args):
        arg_info = []
        for (name, type_), value in zip(motor_mod.shell_commands[name].items(), args):
            type_name = getattr(type_, "__name__", type_)
            arg_info.append(f"({type_name}) {name} = {value!r}")

        # TODO somehow figure out about motor port -> asyn port linking, maybe
        return "\n".join(arg_info)

    def handle_iocshRegisterVariable(self, variable, value, *_):
        self.variables[variable] = value
        return f"Registered variable: {variable!r}={value!r}"

    def env_set_EPICS_BASE(self, path):
        # TODO: slac-specific
        path = str(pathlib.Path(path).resolve())
        version_prefixes = [
            "/reg/g/pcds/epics/base/",
            "/cds/group/pcds/epics/base/",
        ]
        for prefix in version_prefixes:
            if path.startswith(prefix):
                path = path[len(prefix):]
                if "/" in path:
                    path = path.split("/")[0]
                version = path.lstrip("R")
                if self.ioc_info.base_version == settings.DEFAULT_BASE_VERSION:
                    self.ioc_info.base_version = version
                    return f"Set base version: {version}"
                return (
                    f"Found version ({version}) but version already specified:"
                    f" {self.ioc_info.base_version}"
                )

    def handle_epicsEnvSet(self, variable, value, *_):
        self.macro_context.define(**{variable: value})
        hook = getattr(self, f"env_set_{variable}", None)
        if hook and callable(hook):
            hook_result = hook(value)
        else:
            hook_result = ""

        return {
            "variable": variable,
            "value": value,
            "hook": hook_result,
        }

    def handle_epicsEnvShow(self, *_):
        return self.macro_context.get_macros()

    def handle_iocshCmd(self, command, *_):
        return IocshCmdArgs(context=self.get_load_context(), command=command)

    def handle_cd(self, path, *_):
        path = self._fix_path(path)
        if path.is_absolute():
            new_dir = path
        else:
            new_dir = self.working_directory / path

        if not new_dir.exists():
            raise RuntimeError(f"Path does not exist: {new_dir}")
        self.working_directory = new_dir.resolve()
        return f"New working directory: {self.working_directory}"

    handle_chdir = handle_cd

    def handle_iocInit(self, *_):
        if self.ioc_initialized:
            return {
                "success": False,
                "error": "Already initialized",
            }

        result = {
            "success": True,
        }
        self.ioc_initialized = True

        if self.access_security_filename is not None:
            try:
                result["access_security"] = self._load_access_security()
            except Exception as ex:
                result["access_security"] = {
                    "exception_class": type(ex).__name__,
                    "error": str(ex),
                }

        return result

    def handle_asSetSubstitutions(self, macros, *_):
        self.access_security_macros = self.macro_context.definitions_to_dict(
            macros
        )
        return {
            "macros": self.access_security_macros,
            "note": "See iocInit results for details.",
        }

    def handle_asSetFilename(self, filename, *_):
        self.access_security_filename = self._fix_path(filename).resolve()
        return {
            "filename": str(self.access_security_filename),
            "note": "See iocInit results for details.",
        }

    def _load_access_security(self):
        """Load access security settings at iocInit time."""
        filename, contents = self.load_file(self.access_security_filename)
        if self.access_security_macros:
            macro_context = MacroContext(use_environment=False)
            macro_context.define(**self.access_security_macros)
            contents = "\n".join(
                macro_context.expand(line)
                for line in contents.splitlines()
            )

        self.access_security = AccessSecurityConfig.from_string(
            contents, filename=str(filename)
        )
        return {
            "filename": filename,
            "macros": self.access_security_macros,
        }

    def handle_dbLoadDatabase(self, dbd, path=None, substitutions=None, *_):
        if self.ioc_initialized:
            raise RuntimeError("Database cannot be loaded after iocInit")
        if self.database_definition:
            # TODO: technically this is allowed; we'll need to update
            # raise RuntimeError("dbd already loaded")
            return "whatrecord: TODO multiple dbLoadDatabase"
        dbd = self._fix_path_with_search_list(dbd, self.db_include_paths)
        fn, contents = self.load_file(dbd)
        macro_context = MacroContext(use_environment=False)
        macro_context.define_from_string(substitutions or "")
        self.database_definition = Database.from_string(
            contents,
            version=self.ioc_info.database_version_spec,
            filename=fn,
            macro_context=macro_context,
        )

        for addpath in self.database_definition.addpaths:
            for path in addpath.path.split(os.pathsep):  # TODO: OS-dependent
                self.db_add_paths.append((dbd.parent / path).resolve())

        self.aliases.update(self.database_definition.aliases)

        return {"result": f"Loaded database: {fn}"}

    def handle_dbLoadRecords(self, filename, macros="", *_):
        if not self.database_definition:
            raise RuntimeError("dbd not yet loaded")
        if self.ioc_initialized:
            raise RuntimeError("Records cannot be loaded after iocInit")

        filename = self._fix_path_with_search_list(filename, self.db_include_paths)
        filename, contents = self.load_file(filename)

        macro_context = MacroContext(use_environment=False)
        macros = macro_context.define_from_string(macros or "")

        try:
            lint = LinterResults.from_database_string(
                db=contents,
                dbd=self.database_definition,
                db_filename=filename,
                macro_context=macro_context,
                version=self.ioc_info.database_version_spec,
            )
        except Exception as ex:
            # TODO move this around
            raise DatabaseLoadFailure(
                f"Failed to load {filename}: {type(ex).__name__} {ex}"
            ) from ex

        context = self.get_load_context()
        db: Database = lint.db
        for name, rec in db.records.items():
            if name not in self.database:
                self.database[name] = rec
                rec.context = context + rec.context
                rec.owner = self.ioc_info.name
            else:
                entry = self.database[name]
                entry.context = entry.context + rec.context
                entry.fields.update(rec.fields)
                # entry.owner = self.ioc_info.name ?

            self.annotate_record(rec)

        for name, rec in db.pva_groups.items():
            if name not in self.pva_database:
                self.pva_database[name] = rec
                rec.context = context + rec.context
                rec.owner = self.ioc_info.name
            else:
                entry = self.database[name]
                entry.context = entry.context + rec.context
                entry.fields.update(rec.fields)
                # entry.owner = self.ioc_info.name ?

            self.annotate_record(rec)

        self.aliases.update(db.aliases)
        for addpath in db.addpaths:
            for path in addpath.path.split(os.pathsep):  # TODO: OS-dependent
                self.db_add_paths.append((db.parent / path).resolve())

        return {
            "loaded_records": len(db.records),
            "loaded_groups": len(db.pva_groups),
            "linter": lint,
        }

    def annotate_record(self, record: RecordInstance):
        """Hook to annotate a record after being loaded."""
        # rtype = record.record_type
        dtype = record.fields.get("DTYP", None)
        if not dtype:
            return

        if dtype.value == "stream":
            self.annotate_streamdevice(record)

    def annotate_streamdevice(self, record: RecordInstance):
        """Hook for StreamDevice annotation of a given record."""
        info_field = record.fields.get("INP", record.fields.get("OUT", None))
        if not info_field:
            return

        info_field = info_field.value.strip()
        results = {}
        try:
            proto_file, proto_name, *proto_args = split_words(info_field).argv
            proto_file = proto_file.lstrip("@ ")
        except Exception:
            results["error"] = (
                f"Invalid StreamDevice input/output field: {info_field!r}"
            )
            proto_file = None
            proto_name = None
            proto_args = []
        else:
            try:
                protocol = self.load_streamdevice_protocol(proto_file)
            except Exception as ex:
                results["error"] = f"{ex.__class__.__name__}: {ex}"
            else:
                if proto_name in protocol.protocols:
                    results["protocol"] = protocol.protocols[proto_name]
                else:
                    results["error"] = (
                        f"Unknown protocol {proto_name!r} in {proto_file}; "
                        f"options are: {list(protocol.protocols)}"
                    )

        record.metadata["streamdevice"] = {
            "protocol_file": proto_file,
            "protocol_name": proto_name,
            "protocol_args": proto_args,
            **results,
        }

    def load_streamdevice_protocol(
        self,
        filename: Union[str, pathlib.Path]
    ) -> streamdevice.Protocol:
        """Load a StreamDevice protocol file."""
        filename = self._fix_path_with_search_list(
            filename,
            self.paths_from_env_var("STREAM_PROTOCOL_PATH", default=".")
        )
        key = str(filename)
        if key not in self.streamdevice:
            fn, contents = self.load_file(filename)
            self.streamdevice[key] = streamdevice.StreamProtocol.from_string(
                contents,
                filename=fn
            )
        return self.streamdevice[key]

    def handle_dbl(self, rtyp=None, fields=None, *_):
        return []  # list(self.database)

    def handle_NDPvaConfigure(
        self,
        portName=None,
        queueSize=None,
        blockingCallbacks=None,
        NDArrayPort=None,
        NDArrayAddr=None,
        pvName=None,
        maxBuffers=None,
        maxMemory=None,
        priority=None,
        stackSize=None,
        *_,
    ):
        """Implicitly creates a PVA group named ``pvName``."""
        if pvName is None:
            return

        metadata = {
            "portName": portName or "",
            "queueSize": queueSize or "",
            "blockingCallbacks": blockingCallbacks or "",
            "NDArrayPort": NDArrayPort or "",
            "NDArrayAddr": NDArrayAddr or "",
            "pvName": pvName or "",
            "maxBuffers": maxBuffers or "",
            "maxMemory": maxMemory or "",
            "priority": priority or "",
            "stackSize": stackSize or "",
        }
        self.pva_database[pvName] = RecordInstance(
            context=self.get_load_context(),
            name=pvName,
            record_type="PVA",
            fields={},
            is_pva=True,
            metadata={"areaDetector": metadata},
        )
        return metadata

    def handle_drvAsynSerialPortConfigure(
        self,
        portName=None,
        ttyName=None,
        priority=None,
        noAutoConnect=None,
        noProcessEos=None,
        *_,
    ):
        # SLAC-specific, but doesn't hurt anyone
        if not portName:
            return

        self.asyn_ports[portName] = asyn.AsynSerialPort(
            context=self.get_load_context(),
            name=portName,
            ttyName=ttyName,
            priority=priority,
            noAutoConnect=noAutoConnect,
            noProcessEos=noProcessEos,
        )

    def handle_drvAsynIPPortConfigure(
        self,
        portName=None,
        hostInfo=None,
        priority=None,
        noAutoConnect=None,
        noProcessEos=None,
        *_,
    ):
        # SLAC-specific, but doesn't hurt anyone
        if portName:
            self.asyn_ports[portName] = asyn.AsynIPPort(
                context=self.get_load_context(),
                name=portName,
                hostInfo=hostInfo,
                priority=priority,
                noAutoConnect=noAutoConnect,
                noProcessEos=noProcessEos,
            )

    def handle_adsAsynPortDriverConfigure(
        self,
        portName=None,
        ipaddr=None,
        amsaddr=None,
        amsport=None,
        asynParamTableSize=None,
        priority=None,
        noAutoConnect=None,
        defaultSampleTimeMS=None,
        maxDelayTimeMS=None,
        adsTimeoutMS=None,
        defaultTimeSource=None,
        *_,
    ):
        # SLAC-specific, but doesn't hurt anyone
        if portName:
            self.asyn_ports[portName] = asyn.AdsAsynPort(
                context=self.get_load_context(),
                name=portName,
                ipaddr=ipaddr,
                amsaddr=amsaddr,
                amsport=amsport,
                asynParamTableSize=asynParamTableSize,
                priority=priority,
                noAutoConnect=noAutoConnect,
                defaultSampleTimeMS=defaultSampleTimeMS,
                maxDelayTimeMS=maxDelayTimeMS,
                adsTimeoutMS=adsTimeoutMS,
                defaultTimeSource=defaultTimeSource,
            )

    def handle_asynSetOption(self, name, addr, key, value, *_):
        port = self.asyn_ports[name]
        opt = asyn.AsynPortOption(
            context=self.get_load_context(),
            key=key,
            value=value,
        )

        if isinstance(port, asyn.AsynPortMultiDevice):
            port.devices[addr].options[key] = opt
        else:
            port.options[key] = opt

    def handle_drvAsynMotorConfigure(
        self,
        port_name: str = "",
        driver_name: str = "",
        card_num: int = 0,
        num_axes: int = 0,
        *_,
    ):
        self.asyn_ports[port_name] = asyn.AsynMotor(
            context=self.get_load_context(),
            name=port_name,
            parent=None,
            metadata=dict(
                num_axes=num_axes,
                card_num=card_num,
                driver_name=driver_name,
            ),
        )

    def handle_EthercatMCCreateController(
        self,
        motor_port: str = "",
        asyn_port: str = "",
        num_axes: int = 0,
        move_poll_rate: float = 0.0,
        idle_poll_rate: float = 0.0,
        *_,
    ):
        # SLAC-specific
        port = self.asyn_ports[asyn_port]
        motor = asyn.AsynMotor(
            context=self.get_load_context(),
            name=motor_port,
            parent=asyn_port,
            metadata=dict(
                num_axes=num_axes,
                move_poll_rate=move_poll_rate,
                idle_poll_rate=idle_poll_rate,
            ),
        )

        # Tie it to both the original asyn port (as a motor) and also the
        # top-level asyn ports.
        port.motors[motor_port] = motor
        self.asyn_ports[motor_port] = motor


@dataclass
class ScriptContainer:
    """
    Aggregate container for any number of LoadedIoc instances.

    Combines databases, sets of loaded files ease of querying.
    """

    database: Dict[str, RecordInstance] = field(default_factory=dict)
    aliases: Dict[str, str] = field(default_factory=dict)
    pva_database: Dict[str, RecordInstance] = field(default_factory=dict)
    scripts: Dict[str, LoadedIoc] = field(default_factory=dict)
    startup_script_to_ioc: Dict[str, str] = field(default_factory=dict)
    #: absolute filename path to sha
    loaded_files: Dict[str, str] = field(default_factory=dict)
    record_types: Dict[str, RecordType] = field(default_factory=dict)
    pv_relations: PVRelations = field(default_factory=dict)

    def add_loaded_ioc(self, loaded: LoadedIoc):
        ioc_name = loaded.metadata.name
        self.scripts[ioc_name] = loaded
        self.startup_script_to_ioc[str(loaded.metadata.script)] = ioc_name

        # TODO: IOCs will have conflicting definitions of records
        self.aliases.update(loaded.shell_state.aliases)
        if loaded.shell_state.database_definition:
            self.record_types.update(
                loaded.shell_state.database_definition.record_types
            )
        graph.combine_relations(
            self.pv_relations, self.database,
            loaded.pv_relations, loaded.shell_state.database,
            record_types=self.record_types,
            aliases=self.aliases,
        )
        self.database.update(loaded.shell_state.database)
        self.pva_database.update(loaded.shell_state.pva_database)
        self.loaded_files.update(loaded.shell_state.loaded_files)

    def whatrec(
        self,
        rec: str,
        field: Optional[str] = None,
        include_pva: bool = True,
        format_option: str = "console",
        file=sys.stdout,
    ) -> List[WhatRecord]:
        fmt = FormatContext()
        result = []
        for name, loaded in self.scripts.items():
            info: WhatRecord = loaded.whatrec(rec, field, include_pva=include_pva)
            if info is not None:
                info.ioc = loaded.metadata
                for match in [info.record, info.pva_group]:
                    if file is not None and match is not None:
                        print(fmt.render_object(match, format_option), file=file)
                        for asyn_port in info.asyn_ports:
                            print(
                                fmt.render_object(asyn_port, format_option), file=file
                            )
                result.append(info)
        return result


@dataclass
class LoadedIoc:
    name: str
    path: pathlib.Path
    metadata: IocMetadata
    shell_state: ShellState
    script: IocshScript
    load_failure: bool = False
    pv_relations: PVRelations = field(default_factory=dict)

    @classmethod
    def _json_from_cache(cls, md: IocMetadata) -> Optional[dict]:
        try:
            with open(md.ioc_cache_filename, "rb") as fp:
                return json.load(fp)
        except FileNotFoundError:
            ...
        except json.decoder.JSONDecodeError:
            # Truncated output file, perhaps
            ...

    @classmethod
    def from_cache(cls, md: IocMetadata) -> Optional[LoadedIoc]:
        json_dict = cls._json_from_cache(md)
        if json_dict is not None:
            return apischema.deserialize(cls, json_dict)

    def save_to_cache(self) -> bool:
        if not settings.CACHE_PATH:
            return False

        with open(self.metadata.ioc_cache_filename, "wt") as fp:
            json.dump(apischema.serialize(self), fp=fp)
        return True

    @classmethod
    def from_errored_load(
        cls, md: IocMetadata, load_failure: IocLoadFailure
    ) -> LoadedIoc:
        exception_line = f"{load_failure.ex_class}: {load_failure.ex_message}"
        error_lines = [exception_line] + load_failure.traceback.splitlines()
        script = IocshScript(
            path=str(md.script),
            lines=tuple(
                IocshResult(line=line, context=(LoadContext("error", lineno),))
                for lineno, line in enumerate(error_lines, 1)
            ),
        )
        md.metadata["exception_class"] = load_failure.ex_class
        md.metadata["exception_message"] = load_failure.ex_message
        md.metadata["traceback"] = load_failure.traceback
        md.metadata["load_failure"] = True
        return cls(
            name=md.name,
            path=md.script,
            metadata=md,
            shell_state=ShellState(),
            script=script,
            load_failure=True,
        )

    @classmethod
    def from_metadata(cls, md: IocMetadata) -> LoadedIoc:
        sh = ShellState(ioc_info=md)
        sh.working_directory = md.startup_directory
        sh.macro_context.define(**md.macros)
        sh.standin_directories = md.standin_directories or {}

        script = IocshScript.from_metadata(md, sh=sh)
        return cls(
            name=md.name,
            path=md.script,
            metadata=md,
            shell_state=sh,
            script=script,
            pv_relations=graph.build_database_relations(sh.database),
        )

    def whatrec(
        self, rec: str, field: Optional[str] = None, include_pva: bool = True
    ) -> Optional[WhatRecord]:
        """Get record information, optionally including PVAccess results."""
        state = self.shell_state
        v3_inst = state.database.get(state.aliases.get(rec, rec), None)
        pva_inst = state.pva_database.get(rec, None) if include_pva else None
        if not v3_inst and not pva_inst:
            return

        asyn_ports = []
        what = WhatRecord(
            name=rec, asyn_ports=asyn_ports, ioc=self.metadata,
            record=None, pva_group=None,
        )
        if v3_inst is not None:
            if not state.database_definition:
                defn = None
            else:
                defn = state.database_definition.record_types.get(
                    v3_inst.record_type, None
                )
                what.menus = state.database_definition.menus
                # but what about device types and such?

            what.record = RecordDefinitionAndInstance(defn, v3_inst)

            asyn_port = state.get_asyn_port_from_record(v3_inst)
            if asyn_port is not None:
                asyn_ports.append(asyn_port)

                parent_port = getattr(asyn_port, "parent", None)
                if parent_port is not None:
                    asyn_ports.insert(0, state.asyn_ports.get(parent_port, None))

        if pva_inst is not None:
            what.pva_group = pva_inst

        return what


def load_cached_ioc(
    md: IocMetadata,
    allow_failed_load: bool = False,
) -> Optional[LoadedIoc]:
    cached_md = md.from_cache()
    if cached_md is None:
        logger.debug("Cached metadata unavailable %s", md.name)
        return None

    if md._cache_key != cached_md._cache_key:
        logger.error("Cache key mismatch?! %s %s", md._cache_key, cached_md._cache_key)
        return None

    if allow_failed_load and (
        cached_md.metadata.get("load_failure") or md.looks_like_sh
    ):
        logger.debug(
            "%s allow_failed_load=True; %s, md.looks_like_sh=%s",
            md.name,
            cached_md.metadata.get("load_failure"),
            md.looks_like_sh,
        )
    elif not cached_md.is_up_to_date():
        logger.debug("%s is not up-to-date", md.name)
        return

    try:
        logger.debug("%s is up-to-date; load from cache", md.name)
        return LoadedIoc._json_from_cache(cached_md)
    except FileNotFoundError:
        logger.error("%s is noted as up-to-date; but cache file missing", md.name)


@dataclass
class IocLoadFailure:
    ex_class: str
    ex_message: str
    traceback: str


@dataclass
class IocLoadResult:
    identifier: Union[int, str]
    load_time: float
    cache_hit: bool
    result: Union[IocLoadFailure, str]


async def async_load_ioc(
    identifier: Union[int, str],
    md: IocMetadata,
    standin_directories,
    use_gdb: bool = True,
    use_cache: bool = True,
) -> IocLoadResult:
    """
    Helper function for loading an IOC in a subprocess and relying on the cache.
    """
    if not settings.CACHE_PATH:
        use_cache = False
    with time_context() as ctx:
        try:
            md.standin_directories.update(standin_directories)
            if use_cache:
                cached_ioc = load_cached_ioc(md)
                if cached_ioc:
                    return IocLoadResult(
                        identifier=identifier,
                        load_time=ctx(),
                        cache_hit=True,
                        result="use_cache"
                    )

            loaded = LoadedIoc.from_metadata(md)
            if use_gdb:
                await md.get_binary_information()

            if use_cache:
                loaded.metadata.save_to_cache()
                loaded.save_to_cache()
                # Avoid pickling massive JSON blob; instruct server to load
                # from cache with token 'use_cache'
                serialized = "use_cache"
            else:
                serialized = apischema.serialize(loaded)
        except Exception as ex:
            return IocLoadResult(
                identifier=identifier,
                load_time=ctx(),
                cache_hit=False,
                result=IocLoadFailure(
                    ex_class=type(ex).__name__,
                    ex_message=str(ex),
                    traceback=traceback.format_exc(),
                ),
            )

        return IocLoadResult(
            identifier=identifier,
            load_time=ctx(),
            cache_hit=False,
            result=serialized,
        )


def _load_ioc(identifier, md, standin_directories, use_gdb=True, use_cache=True) -> IocLoadResult:
    return asyncio.run(
        async_load_ioc(
            identifier=identifier, md=md,
            standin_directories=standin_directories, use_gdb=use_gdb,
            use_cache=use_cache
        )
    )


def _sigint_handler(signum, frame):
    logger.error("Subprocess killed with SIGINT; exiting.")
    sys.exit(1)


def _process_init():
    signal.signal(signal.SIGINT, _sigint_handler)


async def load_startup_scripts_with_metadata(
    *md_items,
    standin_directories=None,
    processes: int = 8,
    use_gdb: bool = True,
) -> ScriptContainer:
    """
    Load all given startup scripts into a shared ScriptContainer.

    Parameters
    ----------
    *md_items : list of IocMetadata
        List of IOC metadata.
    standin_directories : dict
        Stand-in/substitute directory mapping.
    processes : int
        The number of processes to use when loading.
    """
    total_files = len(md_items)
    total_child_load_time = 0.0

    with time_context() as total_time, ProcessPoolExecutor(
        max_workers=processes, initializer=_process_init
    ) as executor:
        coros = [
            asyncio.wrap_future(
                executor.submit(
                    _load_ioc, identifier=idx, md=md,
                    standin_directories=standin_directories, use_gdb=use_gdb
                )
            )
            for idx, md in enumerate(md_items)
        ]

        for coro in asyncio.as_completed(coros):
            try:
                load_result = await coro
                md = md_items[load_result.identifier]
            except Exception as ex:
                logger.exception(
                    "Internal error while loading: %s: %s [server %.1f s]",
                    type(ex).__name__,
                    ex,
                    total_time(),
                )
                continue

            use_cache = load_result.result == "use_cache"
            if not use_cache:
                loaded = load_result.result
            else:
                try:
                    loaded = load_cached_ioc(md, allow_failed_load=True)
                    if loaded is None:
                        raise ValueError("Cache entry is empty?")
                except Exception as ex:
                    logger.exception(
                        "Internal error while loading cached IOC from disk: "
                        "%s: %s [server %.1f s]",
                        type(ex).__name__,
                        ex,
                        total_time(),
                    )
                    continue

            total_child_load_time += load_result.load_time

            if isinstance(loaded, IocLoadFailure):
                failure_result: IocLoadFailure = loaded
                logger.error(
                    "Failed to load %s in subprocess: %s "
                    "[%.1f s; server %.1f]: %s\n%s",
                    md.name or md.script,
                    failure_result.ex_class,
                    load_result.load_time,
                    total_time(),
                    failure_result.ex_message,
                    (
                        failure_result.traceback
                        if failure_result.ex_class != "FileNotFoundError"
                        else ""
                    ),
                )
                if md.base_version == settings.DEFAULT_BASE_VERSION:
                    md.base_version = "unknown"
                yield md, LoadedIoc.from_errored_load(md, loaded)
                continue

            with time_context() as ctx:
                loaded_ioc = apischema.deserialize(LoadedIoc, loaded)
                logger.info(
                    "Child loaded %s%s in %.1f s, server deserialized in %.1f s",
                    md.name or md.script,
                    " from cache" if load_result.cache_hit else "",
                    load_result.load_time,
                    ctx(),
                )
                yield md, loaded_ioc

    logger.info(
        "Loaded %d startup scripts in %.1f s (wall time) with %d process(es)",
        total_files,
        total_time(),
        processes,
    )
    logger.info(
        "Child processes reported taking a total of %.1f "
        "sec, the total time on %d process(es)",
        total_child_load_time,
        processes,
    )
