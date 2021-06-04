from __future__ import annotations

from dataclasses import field
from typing import ClassVar, Dict, Optional, Union

from .common import AsynPortBase, FrozenLoadContext, dataclass


@dataclass
class AsynPort(AsynPortBase):
    context: FrozenLoadContext
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
    context: FrozenLoadContext
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
    amsport: str = ""
    asynParamTableSize: str = ""
    priority: str = ""
    noAutoConnect: str = ""
    defaultSampleTimeMS: str = ""
    maxDelayTimeMS: str = ""
    adsTimeoutMS: str = ""
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
    context: FrozenLoadContext
    name: str
    metadata: dict = field(default_factory=dict)
    motors: Dict[str, AsynMotor] = field(default_factory=dict)
    devices: Dict[str, AsynPortDevice] = field(default_factory=dict)


@dataclass
class AsynPortDevice(AsynPortBase):
    context: FrozenLoadContext
    name: str = ""
    options: Dict[str, AsynPortOption] = field(default_factory=dict)
    metadata: Dict[str, str] = field(default_factory=dict)
    motors: Dict[str, AsynMotor] = field(default_factory=dict)


@dataclass
class AsynPortOption:
    context: FrozenLoadContext
    key: str
    value: str
