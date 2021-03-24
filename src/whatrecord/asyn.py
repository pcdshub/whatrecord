# cython: language_level=3
import dataclasses
from dataclasses import field
from typing import ClassVar, Dict

from .common import Context


@dataclasses.dataclass
class AsynPort:
    context: Context
    name: str
    options: dict = field(default_factory=dict)
    metadata: dict = field(default_factory=dict)
    motors: dict = field(default_factory=dict)

    _jinja_format_: ClassVar[dict] = {
        "console": """\
AsynPort:
    name: {{name}}
    options: {{options}}
    metadata: {{metadata}}
Defined:
{% for ctx in context %}
    # {{ctx}}
{% endfor %}
{% for motor in motors %}
{% set motor_text = render_object(motor, "console") %}
        {{ motor_text | indent(8)}}
{% endif %}
{% endfor %}
}
""",

    }


@dataclasses.dataclass
class AsynMotor:
    context: Context
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


@dataclasses.dataclass
class AsynPortMultiDevice:
    context: Context
    name: str
    metadata: dict = field(default_factory=dict)
    motors: dict = field(default_factory=dict)
    devices: Dict[str, 'AsynPortDevice'] = field(default_factory=dict)


@dataclasses.dataclass
class AsynPortDevice:
    context: Context
    name: str = ""
    options: dict = field(default_factory=dict)
    metadata: dict = field(default_factory=dict)
    motors: dict = field(default_factory=dict)


@dataclasses.dataclass
class AsynPortOption:
    context: Context
    key: str
    value: str
