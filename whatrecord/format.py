import dataclasses
import inspect
import logging
import textwrap
import typing

import apischema
import jinja2

from .common import LoadContext

logger = logging.getLogger(__name__)


pass_eval_context = (
    jinja2.pass_eval_context
    if hasattr(jinja2, "pass_eval_context")
    else jinja2.evalcontextfilter
)


def template_from_dataclass(cls, fields, render_option):
    """Generate a console-friendly render template from a dataclass."""
    if not fields:
        return f"{cls.__name__}\n"

    name_length = max(len(name) + 1 for name in fields)
    field_text = "\n".join(
        "{% if " + field + " | string | length > 0 %}\n" +
        field.rjust(name_length) +
        ": {% set field_text = render_object(" + field + ", render_option) %}"
        "{{ field_text | indent(name_length + 2) }}"
        "{% endif %}\n"
        for field in fields
    )
    return (
        f"{cls.__name__}:\n"
        f"{{% set name_length = {name_length} %}}\n"
        f"{{% set render_option = {render_option} %}}\n"
        + field_text
    )


class FormatContext:
    def __init__(
        self, helpers=None, *, trim_blocks=True, lstrip_blocks=False,
        default_options="console",
        **env_kwargs
    ):
        self.helpers = helpers or [self.render_object, type, locals]
        self.default_options = default_options
        self._template_dict = {}
        self.env = jinja2.Environment(
            loader=jinja2.DictLoader(self._template_dict),
            trim_blocks=trim_blocks,
            lstrip_blocks=lstrip_blocks,
            **env_kwargs,
        )

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

        if isinstance(obj, typing.Sequence) and not isinstance(obj, str):
            if all(isinstance(obj_idx, LoadContext) for obj_idx in obj):
                # Special-case FullLoadContext
                return " ".join(str(ctx) for ctx in obj)

            return "\n".join(
                f"[{idx}]: " + textwrap.indent(
                    self.render_object(obj_idx, _option, **context),
                    '    '
                ).lstrip()
                for idx, obj_idx in enumerate(obj)
            )

        if isinstance(obj, typing.Mapping):
            return "\n".join(
                f'"{key}": ' + self.render_object(value, _option, **context)
                for key, value in sorted(obj.items())
            )

        if dataclasses.is_dataclass(obj):
            cls = type(obj)
            if cls not in self._fallback_formats:
                # TODO: lazy method here with 'fields'
                serialized = apischema.serialize(obj)
                fields = [
                    field.name
                    for field in dataclasses.fields(obj)
                    if field.name in serialized
                ]
                self._fallback_formats[cls] = template_from_dataclass(
                    cls, fields, option or self.default_options
                )
            return self.render_template(
                self._fallback_formats[cls],
                **context
            )

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
        return context
