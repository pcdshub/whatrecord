from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, ClassVar, Dict, Optional, Union

from .common import (AsynPortBase, FullLoadContext, RecordField,
                     RecordInstance, ShellStateHandler)

logger = logging.getLogger(__name__)


@dataclass
class AsynPort(AsynPortBase):
    context: FullLoadContext
    name: str
    options: Dict[str, AsynPortOption] = field(default_factory=dict)
    metadata: Dict[str, str] = field(default_factory=dict)
    motors: Dict[str, AsynMotor] = field(default_factory=dict)

    _jinja_format_: ClassVar[dict] = {
        "console": """\
{{obj|classname}}:
    name: {{name}}
    options: {{options}}
    metadata: {{metadata}}
    Defined:
{% for ctx in context %}
        * {{ctx}}
{% endfor %}
{% for motor in motors %}
{% set motor_text = render_object(motor, "console") %}
        {{ motor_text | indent(8)}}
{% endfor %}
""",

    }


@dataclass
class AsynMotor(AsynPortBase):
    context: FullLoadContext
    name: str
    metadata: Dict[str, Union[str, int, float]] = field(default_factory=dict)
    parent: Optional[str] = None


@dataclass
class AsynIPPort(AsynPort):
    hostInfo: str = ""
    priority: str = ""
    noAutoConnect: str = ""
    noProcessEos: str = ""


@dataclass
class AsynSerialPort(AsynPort):
    ttyName: str = ""
    priority: str = ""
    noAutoConnect: str = ""
    noProcessEos: str = ""


@dataclass
class AdsAsynPort(AsynPort):
    ipaddr: str = ""
    amsaddr: str = ""
    amsport: int = 0
    asynParamTableSize: int = 0
    priority: int = 0
    noAutoConnect: int = 0
    defaultSampleTimeMS: int = 0
    maxDelayTimeMS: int = 0
    adsTimeoutMS: int = 0
    defaultTimeSource: str = ""

    _jinja_format_: ClassVar[dict] = {
        "console": AsynPort._jinja_format_["console"] + """
    ipaddr: {{ipaddr}}
    amsaddr: {{amsaddr}}
    amsport: {{amsport}}
    asynParamTableSize: {{asynParamTableSize}}
    priority: {{priority}}
    noAutoConnect: {{noAutoConnect}}
    defaultSampleTimeMS: {{defaultSampleTimeMS}}
    maxDelayTimeMS: {{maxDelayTimeMS}}
    adsTimeoutMS: {{adsTimeoutMS}}
    defaultTimeSource: {{defaultTimeSource}}
"""
    }


@dataclass
class AsynPortMultiDevice(AsynPortBase):
    context: FullLoadContext
    name: str
    metadata: dict = field(default_factory=dict)
    motors: Dict[str, AsynMotor] = field(default_factory=dict)
    devices: Dict[str, AsynPortDevice] = field(default_factory=dict)


@dataclass
class AsynPortDevice(AsynPortBase):
    context: FullLoadContext
    name: str = ""
    options: Dict[str, AsynPortOption] = field(default_factory=dict)
    metadata: Dict[str, str] = field(default_factory=dict)
    motors: Dict[str, AsynMotor] = field(default_factory=dict)


@dataclass
class AsynPortOption:
    context: FullLoadContext
    key: str
    value: str


_handler = ShellStateHandler.generic_handler_decorator


@dataclass
class AsynState(ShellStateHandler):
    """
    Asyn IOC shell state handler / container.

    Contains hooks for asyn-related commands and state information.

    Attributes
    ----------
    ports : Dict[str, asyn.AsynPortBase]
        Asyn ports defined by name.
    """
    metadata_key: ClassVar[str] = "asyn"
    ports: Dict[str, AsynPortBase] = field(default_factory=dict)

    @_handler
    def handle_drvAsynSerialPortConfigure(
        self,
        portName: str,
        ttyName: str,
        priority: int = 0,
        noAutoConnect: int = 0,
        noProcessEos: int = 0,
    ):
        # SLAC-specific, but doesn't hurt anyone
        self.ports[portName] = AsynSerialPort(
            context=self.get_load_context(),
            name=portName,
            ttyName=ttyName,
            priority=priority,
            noAutoConnect=noAutoConnect,
            noProcessEos=noProcessEos,
        )

    @_handler
    def handle_drvAsynIPPortConfigure(
        self,
        portName: str,
        hostInfo: str,
        priority: int = 0,
        noAutoConnect: int = 0,
        noProcessEos: int = 0,
    ):
        # SLAC-specific, but doesn't hurt anyone
        self.ports[portName] = AsynIPPort(
            context=self.get_load_context(),
            name=portName,
            hostInfo=hostInfo,
            priority=priority,
            noAutoConnect=noAutoConnect,
            noProcessEos=noProcessEos,
        )

    @_handler
    def handle_asynSetOption(self, name: str, addr: str, key: str, value: str):
        port = self.ports[name]
        opt = AsynPortOption(
            context=self.get_load_context(),
            key=key,
            value=value,
        )

        if isinstance(port, AsynPortMultiDevice):
            port.devices[addr].options[key] = opt
        else:
            port.options[key] = opt

    def get_port_from_record(self, inst: RecordInstance) -> Optional[AsynPort]:
        """Given a record, return its related asyn port."""
        if inst.is_pva:
            return

        rec_field: Optional[RecordField]
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
                return self.ports.get(asyn_port.strip(), None)
            except Exception:
                logger.debug("Failed to parse asyn string", exc_info=True)

    def annotate_record(self, record: RecordInstance) -> Optional[Dict[str, Any]]:
        port = self.get_port_from_record(record)
        if port is not None:
            parent_port = getattr(port, "parent", None)
            ports = [
                port_ for port_ in [parent_port, port]
                if port_ is not None
            ]
            return {"ports": ports}
