# import marshmallow
# import marshmallow_dataclass
import dataclasses
import inspect
import logging

from marshmallow_dataclass import class_schema

from . import asyn, common, db

logger = logging.getLogger(__name__)


_skip_classes = {
    db.MacroContext,
}


def _gather_schemas():
    for module in [db, asyn, common]:
        for attr, cls in inspect.getmembers(module):
            if not inspect.isclass(cls):
                ...
            elif cls not in _skip_classes and dataclasses.is_dataclass(cls):
                print(cls, cls.__name__)
                try:
                    schema = class_schema(cls)()
                except TypeError:
                    logger.debug("Class: %s", cls, exc_info=True)
                    continue

                yield cls, schema


schemas = dict(_gather_schemas())


def serialize(obj):
    if isinstance(obj, dict):
        return {k: serialize(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [serialize(v) for v in obj]

    if dataclasses.is_dataclass(obj):
        # TODO: I feel I'm using these schemas wrong; nested motors dict
        # AsynMotor does not dump properly
        cls = type(obj)
        try:
            schema = schemas[cls]
        except KeyError:
            schema = class_schema(cls)()
            schemas[cls] = schema

        return serialize(schema.dump(obj))
    return obj
