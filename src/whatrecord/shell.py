# cython: language_level=3
import dataclasses
import functools
import logging
import pathlib
from typing import List, Optional

from . import asyn
from . import motor as motor_mod
from .db import DbdFile, load_database_file
from .format import FormatContext
from .iocsh import IocshCommand, IOCShellInterpreter, StateBase

logger = logging.getLogger(__name__)
_dict_field = dataclasses.field(default_factory=dict)


class ShellState(StateBase):
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
    database_definition: DbdFile
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
            method_name = f"handle_{name}"
            if hasattr(self, method_name):
                continue
            method = functools.partial(self._generic_motor_handler, name)
            setattr(self, method_name, method)

    def _generic_motor_handler(self, name, *args):
        for (name, type_), value in zip(motor_mod.shell_commands[name].items(), args):
            ...
        # TODO somehow figure out about motor port -> asyn port linking, maybe

    def handle_iocshRegisterVariable(self, variable, value, *_):
        self.variables[variable] = value

    def handle_epicsEnvSet(self, variable, value, *_):
        self.macro_context.define(**{variable: value})

    def handle_epicsEnvShow(self, *_):
        return {
            str(name, self.string_encoding): str(value, self.string_encoding)
            for name, value in self.macro_context.get_macros().items()
        }

    def handle_iocshCmd(self, command, *_):
        return IocshCommand(context=self.get_short_context(), command=command)

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
        self.database_definition = DbdFile(fn)

    def handle_dbLoadRecords(self, fn, macros, *_):
        if not self.database_definition:
            raise RuntimeError("dbd not yet loaded")
        fn = self._fix_path(fn)

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

        context = tuple(repr(ctx) for ctx in self.load_context)
        for name, rec in linter_results.records.items():
            if name not in self.database:
                self.database[name] = rec
                rec.context = context + rec.context
            else:
                entry = self.database[name]
                entry.context = entry.context + ("and",) + rec.context
                entry.fields.update(rec.fields)

        return linter_results

    def handle_dbl(self, rtyp=None, fields=None, *_):
        return []  # list(self.database)

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
            context=self.get_short_context(),
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
        if not portName:
            return

        self.asyn_ports[portName] = asyn.AsynIPPort(
            context=self.get_short_context(),
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
        if not portName:
            return

        self.asyn_ports[portName] = asyn.AdsAsynPort(
            context=self.get_short_context(),
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
            context=self.get_short_context(),
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
            context=self.get_short_context(),
            name=port_name,
            parent=None,
            metadata=dict(
                num_axes=num_axes,
                card_num=card_num,
                driver_name=driver_name,
            )
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
            context=self.get_short_context(),
            name=motor_port,
            # TODO: would like to reference the object, but dataclasses
            # asdict recursion is tripping me up
            parent=asyn_port,
            metadata=dict(
                num_axes=num_axes,
                move_poll_rate=move_poll_rate,
                idle_poll_rate=idle_poll_rate,
            )
        )

        # Tie it to both the original asyn port (as a motor) and also the
        # top-level asyn ports.
        port.motors[motor_port] = motor
        self.asyn_ports[motor_port] = motor


def whatrec(shell_states: List[ShellState], rec: str, field: Optional[str] = None):
    fmt = FormatContext()
    for state in shell_states:
        inst = state.database.get(rec, None)
        if inst is not None:
            print(fmt.render_object(inst, "console"))

            asyn_port = state.get_asyn_port_from_record(inst)
            if asyn_port is not None:
                print(fmt.render_object(asyn_port, "console"))


def simple_test(fn):
    state = ShellState()
    state.working_directory = pathlib.Path(fn).resolve().parent
    state.macro_context.define(TOP="../..")
    state.standin_directories = {
        "/reg/d/iocCommon/": "/Users/klauer/Repos/iocCommon/",
        "/reg/g/pcds/epics/ioc/common/ads-ioc/R0.3.1/": "/Users/klauer/Repos/ads-ioc/",
        "/reg/g/pcds/epics-dev/zlentz/lcls-plc-kfe-motion/": "/Users/klauer/Repos/lcls-plc-kfe-motion/",  # noqa
    }

    sh = IOCShellInterpreter(state=state)

    with open(fn, "rt") as fp:
        for info, result in sh.interpret_shell_script(fp):
            if info["outputs"]:
                if info["redirects"]:
                    prefix = "[REDIR]"
                elif info.get("filename"):
                    prefix = info["filename"]
                else:
                    prefix = "[OUTPUT]"

                # logger.info("%s%s", prefix, "\n".join(info["outputs"]))
                print(prefix, "\n".join(info["outputs"]))

            if info["error"]:
                logger.error("[ERROR] %s", info["error"])
            if result:
                res_output = repr(result)
                if len(res_output) > 5000:
                    res_output = res_output[:5000] + "..."
                print("->", res_output)
                # logger.info("->", res_output)

    if sh.state.database:
        whatrec([sh.state], list(sh.state.database)[0])
    return sh
