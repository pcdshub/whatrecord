# cython: language_level=3
import dataclasses
from dataclasses import field
from typing import ClassVar, Dict, Tuple

from .common import LoadContext


@dataclasses.dataclass
class AsynPort:
    context: Tuple[LoadContext]
    name: str
    options: dict = field(default_factory=dict)
    metadata: dict = field(default_factory=dict)
    motors: dict = field(default_factory=dict)

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


@dataclasses.dataclass
class AsynMotor:
    context: LoadContext
    name: str
    metadata: dict = field(default_factory=dict)
    parent: AsynPort = None


@dataclasses.dataclass
class AsynIPPort(AsynPort):
    hostInfo: str = ""
    priority: str = ""
    noAutoConnect: str = ""
    noProcessEos: str = ""


@dataclasses.dataclass
class AsynSerialPort(AsynPort):
    ttyName: str = ""
    priority: str = ""
    noAutoConnect: str = ""
    noProcessEos: str = ""


@dataclasses.dataclass
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


@dataclasses.dataclass
class AsynPortMultiDevice:
    context: LoadContext
    name: str
    metadata: dict = field(default_factory=dict)
    motors: Dict[str, AsynMotor] = field(default_factory=dict)
    devices: Dict[str, 'AsynPortDevice'] = field(default_factory=dict)


@dataclasses.dataclass
class AsynPortDevice:
    context: LoadContext
    name: str = ""
    options: Dict[str, str] = field(default_factory=dict)
    metadata: Dict[str, str] = field(default_factory=dict)
    motors: Dict[str, AsynMotor] = field(default_factory=dict)


@dataclasses.dataclass
class AsynPortOption:
    context: LoadContext
    key: str
    value: str
