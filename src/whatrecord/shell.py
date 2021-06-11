from __future__ import annotations

import functools
import inspect
import logging
# import multiprocessing as mp
import os
import pathlib
import sys
import traceback
from dataclasses import dataclass, field
from typing import Callable, Dict, Generator, Iterable, List, Optional

import apischema

from . import asyn, common
from . import motor as motor_mod
from .common import (FullLoadContext, IocMetadata, IocshCommand, IocshResult,
                     IocshScript, MutableLoadContext, RecordInstance,
                     ShortLinterResults, WhatRecord, time_context)
from .db import Database, DatabaseLoadFailure, load_database_file
from .format import FormatContext
from .iocsh import IOCShellLineParser
from .macro import MacroContext

logger = logging.getLogger(__name__)


def _motor_wrapper(method):
    """
    Method decorator for motor-related commands

    Use specific command handler, but also show general parameter information.
    """
    _, name = method.__name__.split("handle_")

    @functools.wraps(method)
    def wrapped(self, *args):
        specific_info = method(self, *args) or ""
        generic_info = self._generic_motor_handler(name, *args)
        if specific_info:
            return f"{specific_info}\n\n{generic_info}"
        return generic_info

    return wrapped


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
    macro_context: MacroContext = field(default_factory=MacroContext,
                                        metadata=apischema.metadata.skip)
    ioc_info: IocMetadata = field(default_factory=IocMetadata)

    _handlers: Dict[str, Callable] = field(default_factory=dict,
                                           metadata=apischema.metadata.skip)
    _parser: IOCShellLineParser = field(default_factory=IOCShellLineParser)

    def __post_init__(self):
        self._handlers.update(dict(self.find_handlers()))
        self._setup_dynamic_handlers()
        self._parser.macro_context = self.macro_context
        self._parser.string_encoding = self.string_encoding

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

    def _handle_input_redirect(self, fileno, redir, shresult, recurse=True,
                               raise_on_error=False):
        filename = self._fix_path(redir["name"])
        try:
            fp_redir = open(filename, "rt")
        except Exception as ex:
            shresult.error = f"{type(ex).__name__}: {filename}"
            yield shresult
            return

        try:
            yield shresult
            yield from self.interpret_shell_script(
                fp_redir, recurse=recurse, name=redir["name"]
            )
        finally:
            fp_redir.close()

    def interpret_shell_line(self, line, recurse=True, raise_on_error=False):
        """Interpret a single shell script line."""
        shresult = self._parser.parse(
            line, context=self.get_load_context(),
            prompt=self.prompt
        )
        input_redirects = [
            (fileno, redir) for fileno, redir in shresult.redirects.items()
            if redir["mode"] == "r"
        ]
        if shresult.error:
            yield shresult
        elif input_redirects:
            if recurse:
                yield from self._handle_input_redirect(
                    *input_redirects[0], shresult, recurse=recurse,
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
                print("\n", type(ex), ex)
                print(ex_details)

            yield shresult
            if isinstance(shresult.result, IocshCommand):
                yield from self.interpret_shell_line(
                    shresult.result.command, recurse=recurse
                )
        else:
            # Otherwise, nothing to do
            yield shresult

    def interpret_shell_script(
        self,
        lines: Iterable[str],
        name: str = "unknown",
        recurse: bool = True,
        raise_on_error: bool = False
    ) -> Generator[IocshResult, None, None]:
        """Interpret a shell script named ``name`` with ``lines`` of text."""
        load_ctx = MutableLoadContext(name, 0)
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
        # return f"No handler for handle_{command}"

    def _fix_path(self, filename: str):
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

    def handle_epicsEnvSet(self, variable, value, *_):
        self.macro_context.define(**{variable: value})
        return f"Defined: {variable!r}={value!r}"

    def handle_epicsEnvShow(self, *_):
        return {
            str(name, self.string_encoding): str(value, self.string_encoding)
            for name, value in self.macro_context.get_macros().items()
        }

    def handle_iocshCmd(self, command, *_):
        return IocshCommand(context=self.get_load_context(), command=command)

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

    def handle_dbLoadDatabase(self, dbd, *_):
        if self.database_definition:
            raise RuntimeError("dbd already loaded")
        fn = self._fix_path(dbd)
        self.database_definition = Database.from_file(fn)
        self.loaded_files[str(fn.resolve())] = str(dbd)
        return f"Loaded database: {fn}"

    def handle_dbLoadRecords(self, fn, macros, *_):
        if not self.database_definition:
            raise RuntimeError("dbd not yet loaded")
        orig_fn = fn
        fn = self._fix_path(fn)
        self.loaded_files[str(fn.resolve())] = str(orig_fn)

        bytes_macros = self.macro_context.definitions_to_dict(
            bytes(macros, self.string_encoding)
        )
        macros = {
            str(variable, self.string_encoding): str(value, self.string_encoding)
            for variable, value in bytes_macros.items()
        }

        try:
            with self.macro_context.scoped(**macros):
                linter_results = load_database_file(
                    dbd=self.database_definition,
                    db=fn,
                    macro_context=self.macro_context,
                )
        except Exception as ex:
            # TODO move this around
            raise DatabaseLoadFailure(
                f"Failed to load {fn}: {type(ex).__name__} {ex}"
            ) from ex

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

    @_motor_wrapper
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

    # @_motor_wrapper  # TODO
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

    @_motor_wrapper
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

    @_motor_wrapper
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

    @_motor_wrapper
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
            # TODO: would like to reference the object, but dataclasses
            # asdict recursion is tripping me up
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
    database: Dict[str, RecordInstance] = field(default_factory=dict)
    pva_database: Dict[str, RecordInstance] = field(default_factory=dict)
    scripts: Dict[str, LoadedIoc] = field(default_factory=dict)

    # TODO: add mtime information for update checking
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


# def _load_startup_script_json(standin_directories, fn) -> Tuple[str, str]:
#     LoadedIoc.from_metadata()
#     return apischema.serialize(startup_lines), apischema.serialize(sh_state)


@dataclass
class LoadedIoc:
    name: str
    path: pathlib.Path
    metadata: IocMetadata
    shell_state: ShellState
    script: IocshScript

    @classmethod
    def from_metadata(cls, md: IocMetadata):
        sh = ShellState(ioc_info=md)
        sh.working_directory = md.startup_directory
        # sh.macro_context.define(TOP="../..")
        sh.standin_directories = md.standin_directories or {}

        with open(md.script, "rt") as fp:
            lines = fp.read().splitlines()

        script = IocshScript(
            path=str(md.script),
            lines=tuple(sh.interpret_shell_script(lines, name=str(md.script))),
        )
        return cls(
            name=md.name,
            path=md.script,
            metadata=md,
            shell_state=sh,
            script=script
        )


def load_startup_scripts(
    *fns, standin_directories=None, processes=1
) -> ScriptContainer:
    """
    Load all given startup scripts into a shared ScriptContainer.

    Parameters
    ----------
    *fns :
        List of filenames to load.
    standin_directories : dict
        Stand-in/substitute directory mapping.
    processes : int
        The number of processes to use when loading.

    Returns
    -------
    container : ScriptContainer
        The resulting container.
    """
    container = ScriptContainer()
    total_files = len(set(fns))

    with time_context() as total_ctx:
        if processes > 1:
            ...
            # loader = functools.partial(_load_startup_script_json, standin_directories)
            # with mp.Pool(processes=processes) as pool:
            #     results = pool.imap(loader, sorted(set(fns)))
            #     for idx, (iocsh_script_raw, sh_state_raw) in enumerate(results, 1):
            #         iocsh_script = apischema.deserialize(
            #             IocshScript, iocsh_script_raw)
            #         sh_state = apischema.deserialize(ShellState, sh_state_raw)
            #         print(f"{idx}/{total_files}: Loaded {iocsh_script.path}")
            #         container.add_script(iocsh_script, sh_state)
        else:
            for idx, fn in enumerate(sorted(set(fns)), 1):
                print(f"{idx}/{total_files}: Loading {fn}...", end="")
                with time_context() as ctx:
                    loaded = LoadedIoc.from_metadata(
                        common.IocMetadata.from_filename(
                            fn,
                            standin_directories=standin_directories
                        )
                    )
                    container.add_script(loaded)
                print(f"[{ctx():.1f} s]")

        print(
            f"Loaded {total_files} startup scripts in {total_ctx():.1f} s "
            f"with {processes} process(es)"
        )
    return container
