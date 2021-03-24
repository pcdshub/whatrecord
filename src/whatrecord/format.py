import dataclasses
import logging

import jinja2

logger = logging.getLogger(__name__)


class FormatContext:
    def __init__(
        self, helpers=None, *, trim_blocks=True, lstrip_blocks=True, **env_kwargs
    ):
        self.helpers = helpers or [self.render_object, type, locals]
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

        @jinja2.evalcontextfilter
        def title_fill(eval_ctx, text, fill_char):
            return fill_char * len(text)

        @jinja2.evalcontextfilter
        def render_object(eval_ctx, obj, option):
            return self.render_object(obj, option)

        return {
            key: value
            for key, value in locals().items()
            if not key.startswith("_") and key not in {"self"}
        }

    def render_template(self, template: str, /, **context):
        for key, value in self.default_render_context.items():
            context.setdefault(key, value)
        self._template_dict["template"] = template
        return self.env.get_template("template").render(context)

    def _render_object_fallback(self, obj, option, **context):
        if dataclasses.is_dataclass(obj):
            if type(obj) not in self._fallback_formats:
                fmt = [f"{obj.__class__.__name__}",] + [   # noqa: E231
                    "%12s: {{%s}}" % (field, field) for field in dataclasses.asdict(obj)
                ]
                self._fallback_formats[type(obj)] = "\n".join(fmt)

            return self.render_template(self._fallback_formats[type(obj)], **context)

        return str(obj)

    def render_object(self, obj, option, /, **context):
        if dataclasses.is_dataclass(obj):
            for field in dataclasses.fields(obj):
                context.setdefault(field.name, getattr(obj, field.name))

        try:
            template = obj._jinja_format_[option]
        except (AttributeError, KeyError):
            return self._render_object_fallback(obj, option, **context)

        return self.render_template(template, **context)

    def get_render_context(self) -> dict:
        """Jinja template context dictionary - helper functions."""
        context = {func.__name__: func for func in self.helpers}
        return context
