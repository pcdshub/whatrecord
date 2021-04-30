import dataclasses
import functools
import logging
import pathlib
import sys
import time
from typing import Dict, Optional

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


@dataclasses.dataclass
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

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self._setup_dynamic_handlers()

    def _setup_dynamic_handlers(self):
        # Just motors for now
        for name, args in motor_mod.shell_commands.items():
            if name not in self.handlers:
                self.handlers[name] = functools.partial(
                    self._generic_motor_handler, name
                )

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
        self.loaded_files[fn.resolve()] = dbd
        return f"Loaded database: {fn}"

    def handle_dbLoadRecords(self, fn, macros, *_):
        if not self.database_definition:
            raise RuntimeError("dbd not yet loaded")
        orig_fn = fn
        fn = self._fix_path(fn)
        self.loaded_files[fn.resolve()] = orig_fn

        bytes_macros = self.macro_context.definitions_to_dict(
            bytes(macros, self.string_encoding)
        )
        macros = {
            str(variable, self.string_encoding): str(value, self.string_encoding)
            for variable, value in bytes_macros.items()
        }
        with self.macro_context.scoped(**macros):
            linter_results = load_database_file(
                dbd=self.database_definition, db=fn, macro_context=self.macro_context
            )

        context = self.get_frozen_context()
        for name, rec in linter_results.records.items():
            if name not in self.database:
                self.database[name] = rec
                rec.context = context + rec.context
            else:
                entry = self.database[name]
                entry.context = entry.context + ("and",) + rec.context
                entry.fields.update(rec.fields)

        return ShortLinterResults.from_full_results(
            linter_results,
            macros=macros
        )

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

    def __init__(self, shell: IOCShellInterpreter):
        self.shell = shell
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
    return WhatRecord(
        owner=None,
        instance=inst,
        asyn_ports=asyn_ports,
    )


def load_startup_scripts(*fns) -> ScriptContainer:
    sh = IOCShellInterpreter()
    container = ScriptContainer(sh)

    total_files = len(fns)
    for idx, fn in enumerate(sorted(set(fns))):
        t0 = time.monotonic()
        if idx == 20:
            break
        print(f"{idx}/{total_files}: Loading {fn}...", end="")
        sh.state = ShellState()
        sh.state.working_directory = pathlib.Path(fn).resolve().parent
        sh.state.macro_context.define(TOP="../..")
        sh.state.standin_directories = {
            # "/reg/d/iocCommon/": "/Users/klauer/Repos/iocCommon/",
            # "/reg/g/pcds/epics/ioc/common/ads-ioc/R0.3.1/": "/Users/klauer/Repos/ads-ioc/",  # noqa
            # "/reg/g/pcds/epics-dev/zlentz/lcls-plc-kfe-motion/": "/Users/klauer/Repos/lcls-plc-kfe-motion/",  # noqa
        }
        with open(fn, "rt") as fp:
            lines = fp.read().splitlines()

        startup = tuple(sh.interpret_shell_script(lines, name=fn))
        container.add_script(IocshScript(path=str(fn), lines=startup), sh.state)
        elapsed = time.monotonic() - t0
        print(f"[{elapsed:.1f} s]")
        # for result in sh.interpret_shell_script(lines, name=fn):
        #     if result.outputs:
        #         if result.redirects:
        #             prefix = "[REDIR]"
        #         else:
        #             prefix = "[OUTPUT]"

        #         logger.info("%s%s", prefix, "\n".join(result.outputs))
        #         # print(prefix, "\n".join(result.outputs))

        #     if result.error:
        #         logger.error("[ERROR] %s", result.error)
        #     if result:
        #         res_output = repr(result)
        #         if len(res_output) > 5000:
        #             res_output = res_output[:5000] + "..."
        #         # print("->", res_output)
        #         # logger.info("->", res_output)
        # print(schema.serialize(sh.state))

    return container
