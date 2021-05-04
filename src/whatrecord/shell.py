import functools
import inspect
import logging
import multiprocessing as mp
import os
import pathlib
import sys
import time
from typing import Dict, Optional, Tuple

from . import asyn
from . import motor as motor_mod
# from . import schema
from .common import (IocshScript, RecordInstance, ShellStateBase,
                     ShortLinterResults, WhatRecord)
from .db import Database, load_database_file
from .format import FormatContext
from .iocsh import IocshCommand, IOCShellInterpreter

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


class ShellState(ShellStateBase):
    """
    Shell state for IOCShellInterpreter.

    Contains hooks for commands and state information.

    Parameters
    ----------
    shell : IOCShellInterpreter, optional
        The interpreter instance this belongs to.
    prompt : str, optional
        The prompt - PS1 - as in "epics>".
    string_encoding : str, optional
        String encoding for byte strings and files.
    variables : dict, optional
        Starting state for variables (not environment variables).

    Attributes
    ----------
    shell: IOCShellInterpreter
        The interpreter instance this belongs to.
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
    load_context: List[LoadContext]
        Current loading context stack (e.g., ``st.cmd`` then ``common_startup.cmd``)
    """

    def __init__(self, shell=None, macro_context=None, **kwargs):
        super().__init__(**kwargs)
        from .macro import MacroContext

        # self._shell = shell
        self._macro_context = macro_context or MacroContext()
        self._handlers = dict(self.find_handlers())
        self._setup_dynamic_handlers()

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

    def get_frozen_context(self):
        if not self.load_context:
            return tuple()
        return tuple(ctx.freeze() for ctx in self.load_context)

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
        self._macro_context.define(**{variable: value})
        return f"Defined: {variable!r}={value!r}"

    def handle_epicsEnvShow(self, *_):
        return {
            str(name, self.string_encoding): str(value, self.string_encoding)
            for name, value in self._macro_context.get_macros().items()
        }

    def handle_iocshCmd(self, command, *_):
        return IocshCommand(context=self.get_frozen_context(), command=command)

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

        bytes_macros = self._macro_context.definitions_to_dict(
            bytes(macros, self.string_encoding)
        )
        macros = {
            str(variable, self.string_encoding): str(value, self.string_encoding)
            for variable, value in bytes_macros.items()
        }
        with self._macro_context.scoped(**macros):
            linter_results = load_database_file(
                dbd=self.database_definition, db=fn, macro_context=self._macro_context
            )

        context = self.get_frozen_context()
        for name, rec in linter_results.records.items():
            if name not in self.database:
                self.database[name] = rec
                rec.context = context + rec.context
            else:
                entry = self.database[name]
                entry.context = entry.context + rec.context
                entry.fields.update(rec.fields)

        return ShortLinterResults.from_full_results(linter_results, macros=macros)

    def handle_dbl(self, rtyp=None, fields=None, *_):
        return []  # list(self.database)

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
            context=self.get_frozen_context(),
            name=portName,
            ttyName=ttyName,
            priority=priority,
            noAutoConnect=noAutoConnect,
            noProcessEos=noProcessEos,
        )

    @_motor_wrapper
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
                context=self.get_frozen_context(),
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
                context=self.get_frozen_context(),
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
            context=self.get_frozen_context(),
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
            context=self.get_frozen_context(),
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
            context=self.get_frozen_context(),
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


class ScriptContainer:
    shell: IOCShellInterpreter
    database: Dict[str, RecordInstance]
    script_to_state: Dict[pathlib.Path, ShellState]
    scripts: Dict[pathlib.Path, IocshScript]
    loaded_files: Dict[str, str]

    def __init__(self, shell: Optional[IOCShellInterpreter] = None):
        self.shell = shell or IOCShellInterpreter()
        self.database = {}
        self.scripts = {}
        self.script_to_state = {}
        self.loaded_files = {}

    def add_script(self, script: IocshScript, shell_state: ShellState):
        path = script.path
        self.scripts[path] = script
        self.script_to_state[path] = shell_state
        self.database.update(shell_state.database)
        self.loaded_files.update(shell_state.loaded_files)

    def whatrec(
        self,
        rec: str,
        field: Optional[str] = None,
        format_option: str = "console",
        file=sys.stdout,
    ):
        fmt = FormatContext()
        result = []
        for stcmd, state in self.script_to_state.items():
            info = whatrec(state, rec, field)
            if info is not None:
                info.owner = str(stcmd)
                inst = info.instance
                if file is not None:
                    print(fmt.render_object(inst, format_option), file=file)
                    for asyn_port in info.asyn_ports:
                        print(fmt.render_object(asyn_port, format_option), file=file)
                result.append(info)
        return result


def whatrec(
    state: ShellState, rec: str, field: Optional[str] = None
) -> Optional[Dict[str, WhatRecord]]:
    """Get record information."""
    inst = state.database.get(rec, None)
    if inst is None:
        return

    asyn_ports = []
    asyn_port = state.get_asyn_port_from_record(inst)
    if asyn_port is not None:
        asyn_ports.append(asyn_port)

        parent_port = getattr(asyn_port, "parent", None)
        if parent_port is not None:
            asyn_ports.insert(0, state.asyn_ports.get(parent_port, None))
    print(asyn_ports)
    return WhatRecord(
        owner=None,
        instance=inst,
        asyn_ports=[]  # asyn_ports,
    )


def load_startup_script(standin_directories, fn) -> Tuple[IocshScript, ShellState]:
    sh = IOCShellInterpreter()
    sh.state = ShellState()
    sh.state.working_directory = pathlib.Path(fn).resolve().parent
    sh.state.macro_context.define(TOP="../..")
    sh.state.standin_directories = standin_directories or {}

    with open(fn, "rt") as fp:
        lines = fp.read().splitlines()

    iocsh_script = IocshScript(
        path=str(fn),
        lines=tuple(sh.interpret_shell_script(lines, name=fn)),
    )
    return iocsh_script, sh.state


def _load_startup_script_json(standin_directories, fn) -> Tuple[str, str]:
    startup_lines, sh_state = load_startup_script(standin_directories, fn)
    return startup_lines.to_json(), sh_state.to_json()


def load_startup_scripts(
    *fns, standin_directories=None, processes=1
) -> ScriptContainer:
    container = ScriptContainer()
    total_files = len(set(fns))

    if processes > 1:
        loader = functools.partial(_load_startup_script_json, standin_directories)
        with mp.Pool(processes=processes) as pool:
            results = pool.imap(loader, sorted(set(fns)))
            for idx, (iocsh_script_raw, sh_state_raw) in enumerate(results, 1):
                iocsh_script = IocshScript.from_json(iocsh_script_raw)
                sh_state = ShellState.from_json(sh_state_raw)
                print(f"{idx}/{total_files}: Loaded {iocsh_script.path}")
                container.add_script(iocsh_script, sh_state)

            return container

    loader = functools.partial(load_startup_script, standin_directories)
    for idx, fn in enumerate(sorted(set(fns)), 1):
        t0 = time.monotonic()
        if idx == 20:
            break
        print(f"{idx}/{total_files}: Loading {fn}...", end="")
        iocsh_script, sh_state = loader(fn)
        container.add_script(iocsh_script, sh_state)
        elapsed = time.monotonic() - t0
        print(f"[{elapsed:.1f} s]")

        t0 = time.monotonic()
        as_json = sh_state.json()
        t1 = time.monotonic()
        sh_state.parse_raw(as_json)
        t2 = time.monotonic()
        print("to json", t1 - t0, "from json", t2 - t1)
        # print(as_json)
        print("size", len(as_json) / 1024, "kb")
        # sh_state.from_json(sh_state.to_json()).to_json()

    return container
