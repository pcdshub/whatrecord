import dataclasses
import functools
import inspect
import json
import logging
import textwrap
import typing
from typing import Optional

import apischema
import jinja2

from . import settings
from .common import LoadContext

logger = logging.getLogger(__name__)


pass_eval_context = (
    jinja2.pass_eval_context
    if hasattr(jinja2, "pass_eval_context")
    else jinja2.evalcontextfilter
)


@dataclasses.dataclass
class FormatOptions:
    indent: int = settings.INDENT


class FormatContext:
    format_options: FormatOptions

    def __init__(
        self,
        helpers: Optional[list] = None,
        options: Optional[FormatOptions] = None,
        *,
        trim_blocks: bool = True,
        lstrip_blocks: bool = False,
        default_options: str = "console",
        **env_kwargs
    ):
        self.helpers = helpers or [self.render_object, type, locals, json]
        self.default_options = default_options
        self._template_dict = {}
        self.env = jinja2.Environment(
            loader=jinja2.DictLoader(self._template_dict),
            trim_blocks=trim_blocks,
            lstrip_blocks=lstrip_blocks,
            **env_kwargs,
        )

        self.format_options = options or FormatOptions()
        self.env.filters.update(self.get_filters())
        self.default_render_context = self.get_render_context()
        self._fallback_formats = {}

    def get_filters(self, **user_config):
        """All jinja filters."""

        @pass_eval_context
        def title_fill(eval_ctx, text, fill_char):
            return fill_char * len(text)

        @pass_eval_context
        def classname(eval_ctx, obj):
            if inspect.isclass(obj):
                return obj.__name__
            return type(obj).__name__

        @pass_eval_context
        def render_object(eval_ctx, obj, option):
            return self.render_object(obj, option)

        return {
            key: value
            for key, value in locals().items()
            if not key.startswith("_") and key not in {"self"}
        }

    def render_template(self, _template: str, **context):
        # TODO: want this to be positional-only; fallback here for pypy
        template = _template

        for key, value in self.default_render_context.items():
            context.setdefault(key, value)
        context["render_ctx"] = context
        return self.env.from_string(template).render(context)

    def _render_object_fallback(self, _obj, _option, **context):
        # TODO: want this to be positional-only; fallback here for pypy
        obj, option = _obj, _option

        def render_prefixed(sub_obj, prefix: str) -> str:
            return textwrap.indent(
                self.render_object(sub_obj, option, **context),
                prefix=prefix,
            )

        if isinstance(obj, typing.Sequence) and not isinstance(obj, str):
            if all(isinstance(obj_idx, LoadContext) for obj_idx in obj):
                # Special-case FullLoadContext
                return " ".join(str(ctx) for ctx in obj)

            return "\n".join(
                f"[{idx}]: " + render_prefixed(obj_idx, '    ').lstrip()
                for idx, obj_idx in enumerate(obj)
            )

        if isinstance(obj, typing.Mapping):
            return "\n".join(
                f'"{key}": ' + render_prefixed(value, " " * (len(key) + 4))
                for key, value in sorted(obj.items())
            )

        if dataclasses.is_dataclass(obj):
            serialized = apischema.serialize(obj)
            return json.dumps(serialized, indent=self.format_options.indent)

        return str(obj)

    def render_object(self, _obj, _option=None, **context):
        # TODO: want this to be positional-only; fallback here for pypy
        obj, option = _obj, _option
        if option is None:
            option = self.default_options

        if dataclasses.is_dataclass(obj):
            for field in dataclasses.fields(obj):
                context.setdefault(field.name, getattr(obj, field.name))

        context.setdefault("obj", obj)

        try:
            template = obj._jinja_format_[option]
        except (AttributeError, KeyError):
            ...
        else:
            return self.render_template(template, **context)

        return self._render_object_fallback(obj, option, **context)

    def get_render_context(self) -> dict:
        """Jinja template context dictionary - helper functions."""
        context = {func.__name__: func for func in self.helpers}
        context["_fmt"] = self.format_options
        context["_json_dump"] = functools.partial(json.dumps, indent=self.format_options.indent)
        context["_indent"] = self.format_options.indent * " "
        return context
