from __future__ import annotations

import asyncio
import functools
import inspect
import json
import logging
import os
import pathlib
import sys
import traceback
from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass, field
from typing import (Callable, Dict, Generator, Iterable, List, Optional, Tuple,
                    Union)

import apischema

from . import asyn
from . import motor as motor_mod
from . import settings, util
from .common import (FullLoadContext, IocMetadata, IocshCmdArgs, IocshRedirect,
                     IocshResult, IocshScript, LoadContext, MutableLoadContext,
                     RecordInstance, ShortLinterResults, WhatRecord,
                     time_context)
from .db import Database, DatabaseLoadFailure, LinterResults
from .format import FormatContext
from .iocsh import parse_iocsh_line
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
    prompt: str
        The prompt - PS1 - as in "epics>".
    variables: dict
        Shell variables.
    string_encoding: str
        String encoding for byte strings and files.
    macro_context: MacroContext
        Macro context for commands that are evaluated.
    standin_directories: dict
        Rewrite hard-coded directory prefixes by setting::

            standin_directories = {"/replace_this/": "/with/this"}
    working_directory: pathlib.Path
        Current working directory.
    database_definition: Database
        Loaded database definition (dbd).
    database: Dict[str, RecordInstance]
        The IOC database of records.
    load_context: List[MutableLoadContext]
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
    database_definition: Optional[Database] = None
    database: Dict[str, RecordInstance] = field(default_factory=dict)
    pva_database: Dict[str, RecordInstance] = field(default_factory=dict)
    load_context: List[MutableLoadContext] = field(default_factory=list)
    asyn_ports: Dict[str, asyn.AsynPortBase] = field(default_factory=dict)
    loaded_files: Dict[str, str] = field(
        default_factory=dict,
    )
    macro_context: MacroContext = field(
        default_factory=MacroContext,
        metadata=apischema.metadata.skip
    )
    ioc_info: IocMetadata = field(default_factory=IocMetadata)

    _handlers: Dict[str, Callable] = field(
        default_factory=dict,
        metadata=apischema.metadata.skip
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

    def load_file(
        self,
        filename: Union[pathlib.Path, str]
    ) -> Tuple[pathlib.Path, str]:
        """Load a file, record its hash, and return its contents."""
        filename = self._fix_path(filename)
        filename = filename.resolve()
        shasum, contents = util.read_text_file_with_hash(
            filename,
            encoding=self.string_encoding
        )
        self.loaded_files[str(filename)] = shasum
        self.ioc_info.loaded_files[str(filename)] = shasum
        return filename, contents

    def _handle_input_redirect(
        self,
        redir: IocshRedirect,
        shresult: IocshResult,
        recurse: bool = True,
        raise_on_error: bool = False
    ):
        try:
            filename, contents = self.load_file(redir.name)
        except Exception as ex:
            shresult.error = f"{type(ex).__name__}: {redir.name}"
            yield shresult
            return

        yield shresult
        yield from self.interpret_shell_script_text(
            contents.splitlines(),
            recurse=recurse,
            name=filename
        )

    def interpret_shell_line(self, line, recurse=True, raise_on_error=False):
        """Interpret a single shell script line."""
        shresult = parse_iocsh_line(
            line, context=self.get_load_context(),
            prompt=self.prompt,
            macro_context=self.macro_context,
            string_encoding=self.string_encoding,
        )
        input_redirects = [
            redir for redir in shresult.redirects
            if redir.mode == "r"
        ]
        if shresult.error:
            yield shresult
        elif input_redirects:
            if recurse:
                yield from self._handle_input_redirect(
                    input_redirects[0], shresult, recurse=recurse,
                    raise_on_error=raise_on_error
                )
        elif shresult.argv:
            try:
                shresult.result = self.handle_command(*shresult.argv)
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
        raise_on_error: bool = False
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
        raise_on_error: bool = False
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

    def get_asyn_port_from_record(self, inst: RecordInstance):
        rec_field = inst.fields.get("INP", inst.fields.get("OUT", None))
        if rec_field is None:
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
        self.ioc_initialized = True

    def handle_dbLoadDatabase(self, dbd, path=None, substitutions=None, *_):
        if self.ioc_initialized:
            raise RuntimeError("Database cannot be loaded after iocInit")
        if self.database_definition:
            # TODO: technically this is allowed; we'll need to update
            # raise RuntimeError("dbd already loaded")
            return "whatrecord: TODO multiple dbLoadDatabase"
        # TODO: handle path - see dbLexRoutines.c
        # env vars: EPICS_DB_INCLUDE_PATH, fallback to "."
        fn, contents = self.load_file(dbd)
        macros = (
            self.macro_context.definitions_to_dict(substitutions)
            if substitutions else {}
        )
        with self.macro_context.scoped(**macros):
            self.database_definition = Database.from_string(
                contents,
                version=self.ioc_info.database_version_spec,
                filename=fn
            )

        return f"Loaded database: {fn}"

    def handle_dbLoadRecords(self, filename, macros, *_):
        if not self.database_definition:
            raise RuntimeError("dbd not yet loaded")
        if self.ioc_initialized:
            raise RuntimeError("Records cannot be loaded after iocInit")
        filename, contents = self.load_file(filename)
        macros = self.macro_context.definitions_to_dict(macros)

        # TODO: refactor as this was pulled out of load_database_file
        try:
            with self.macro_context.scoped(**macros):
                db = Database.from_file(
                    filename, dbd=self.database_definition,
                    macro_context=self.macro_context,
                    version=self.ioc_info.database_version_spec,
                )
        except Exception as ex:
            # TODO move this around
            raise DatabaseLoadFailure(
                f"Failed to load {filename}: {type(ex).__name__} {ex}"
            ) from ex

        linter_results = LinterResults(
            record_types=self.database_definition.record_types,
            # {'ao':{'Soft Channel':'CONSTANT', ...}, ...}
            # recdsets=dbd.devices,  # TODO
            # {'inst:name':'ao', ...}
            records=db.records,
            pva_groups=db.pva_groups,
            extinst=[],
            errors=[],
            warnings=[],
        )

        context = self.get_load_context()
        for name, rec in linter_results.records.items():
            if name not in self.database:
                self.database[name] = rec
                rec.context = context + rec.context
            else:
                entry = self.database[name]
                entry.context = entry.context + rec.context
                entry.fields.update(rec.fields)

        for name, rec in linter_results.pva_groups.items():
            if name not in self.pva_database:
                self.pva_database[name] = rec
                rec.context = context + rec.context
            else:
                entry = self.database[name]
                entry.context = entry.context + rec.context
                entry.fields.update(rec.fields)

        return ShortLinterResults.from_full_results(linter_results, macros=macros)

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
            metadata={
                "areaDetector": metadata
            }
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
    pva_database: Dict[str, RecordInstance] = field(default_factory=dict)
    scripts: Dict[str, LoadedIoc] = field(default_factory=dict)
    #: absolute filename path to sha
    loaded_files: Dict[str, str] = field(default_factory=dict)

    def add_script(self, loaded: LoadedIoc):
        self.scripts[str(loaded.metadata.script)] = loaded
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
        for stcmd, loaded in self.scripts.items():
            info = whatrec(
                loaded.shell_state, rec, field, include_pva=include_pva
            )
            if info is not None:
                info.owner = str(stcmd)
                info.ioc = loaded.metadata
                for inst in info.instances:
                    if file is not None:
                        print(fmt.render_object(inst, format_option), file=file)
                        for asyn_port in info.asyn_ports:
                            print(fmt.render_object(asyn_port, format_option),
                                  file=file)
                result.append(info)
        return result


def whatrec(
    state: ShellState, rec: str, field: Optional[str] = None,
    include_pva: bool = True
) -> Optional[WhatRecord]:
    """Get record information."""
    v3_inst = state.database.get(rec, None)
    pva_inst = state.pva_database.get(rec, None) if include_pva else None
    if not v3_inst and not pva_inst:
        return

    asyn_ports = []
    instances = []
    if v3_inst is not None:
        instances.append(v3_inst)
        asyn_port = state.get_asyn_port_from_record(v3_inst)
        if asyn_port is not None:
            asyn_ports.append(asyn_port)

            parent_port = getattr(asyn_port, "parent", None)
            if parent_port is not None:
                asyn_ports.insert(0, state.asyn_ports.get(parent_port, None))

    if pva_inst is not None:
        instances.append(pva_inst)

    return WhatRecord(
        name=rec,
        owner=None,
        instances=instances,
        asyn_ports=asyn_ports,
        ioc=None
    )


@dataclass
class LoadedIoc:
    name: str
    path: pathlib.Path
    metadata: IocMetadata
    shell_state: ShellState
    script: IocshScript

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
        cls,
        md: IocMetadata,
        load_failure: IocLoadFailure
    ) -> LoadedIoc:
        exception_line = f"{load_failure.ex_class}: {load_failure.ex_message}"
        error_lines = [exception_line] + load_failure.traceback.splitlines()
        script = IocshScript(
            path=str(md.script),
            lines=tuple(
                IocshResult.from_line(line, context=(LoadContext("error", lineno),))
                for lineno, line in enumerate(error_lines, 1)
            ),
        )
        md.metadata["exception_class"] = load_failure.ex_class
        md.metadata["exception_message"] = load_failure.ex_message
        md.metadata["traceback"] = load_failure.traceback
        return cls(
            name=md.name,
            path=md.script,
            metadata=md,
            shell_state=ShellState(),
            script=script
        )

    @classmethod
    def from_metadata(cls, md: IocMetadata) -> LoadedIoc:
        sh = ShellState(ioc_info=md)
        sh.working_directory = md.startup_directory
        sh.macro_context.define(**md.macros)
        sh.standin_directories = md.standin_directories or {}

        script = IocshScript.from_metadata(
            md,
            sh=sh
        )

        return cls(
            name=md.name,
            path=md.script,
            metadata=md,
            shell_state=sh,
            script=script,
        )


@dataclass
class IocLoadFailure:
    ex_class: str
    ex_message: str
    traceback: str


def _load_ioc(identifier, md, standin_directories, use_gdb=True,
              use_cache=True):

    def load_cached_ioc():
        cached_md = md.from_cache()
        if cached_md is not None:
            assert md._cache_key == cached_md._cache_key
            if cached_md.is_up_to_date():
                try:
                    return LoadedIoc._json_from_cache(cached_md)
                except FileNotFoundError:
                    ...

    async def _load():
        with time_context() as ctx:
            try:
                md.standin_directories.update(standin_directories)
                if use_gdb:
                    await md.get_binary_information()
                if use_cache:
                    cached_ioc = load_cached_ioc()
                    if cached_ioc:
                        return identifier, ctx(), cached_ioc

                loaded = LoadedIoc.from_metadata(md)
                serialized = apischema.serialize(loaded)
                if use_cache:
                    loaded.metadata.save_to_cache()
                    loaded.save_to_cache()
            except Exception as ex:
                result = IocLoadFailure(
                    ex_class=type(ex).__name__, ex_message=str(ex),
                    traceback=traceback.format_exc()
                )
                return identifier, ctx(), result

            return identifier, ctx(), serialized

    return asyncio.run(_load())


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

    with time_context() as total_ctx, ProcessPoolExecutor(
        max_workers=processes
    ) as executor:
        coros = [
            asyncio.wrap_future(
                executor.submit(
                    _load_ioc, idx, md, standin_directories, use_gdb=use_gdb
                )
            )
            for idx, md in enumerate(md_items)
        ]

        for completed_count, coro in enumerate(asyncio.as_completed(coros), 1):
            try:
                script_idx, load_elapsed, loaded_ser = await coro
                md = md_items[script_idx]
            except Exception as ex:
                logger.exception(
                    "Internal error while loading: %s: %s",
                    type(ex).__name__,
                    ex,
                )
                continue

            total_child_load_time += load_elapsed

            if isinstance(loaded_ser, IocLoadFailure):
                failure_result: IocLoadFailure = loaded_ser
                logger.error(
                    "Failed to load %s in subprocess: %s [%.1f s]: %s\n%s",
                    md.name or md.script,
                    failure_result.ex_class,
                    load_elapsed,
                    failure_result.ex_message,
                    failure_result.traceback,
                )
                if md.base_version == settings.DEFAULT_BASE_VERSION:
                    md.base_version = "unknown"
                yield md, LoadedIoc.from_errored_load(md, loaded_ser)
                continue

            with time_context() as ctx:
                loaded_ioc = apischema.deserialize(LoadedIoc, loaded_ser)
                logger.info(
                    "Loaded %s in %.1f s, deserialized in %.1f s",
                    md.name or md.script, load_elapsed, ctx()
                )
                yield md, loaded_ioc

    logger.info(
        "Loaded %d startup scripts in %.1f s (wall time) with %d process(es)",
        total_files, total_ctx(), processes
    )
    logger.info(
        "Child processes reported taking a total of %.1f "
        "sec, the total time on %d process(es)",
        total_child_load_time, processes
    )
