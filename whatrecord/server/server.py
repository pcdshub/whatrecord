import asyncio
import collections
import dataclasses
import fnmatch
import functools
import json
import logging
import re
import sys
import tempfile
from typing import (Any, ClassVar, DefaultDict, Dict, List, Optional, Set,
                    Tuple, Union)

import apischema
import graphviz
from aiohttp import web

from .. import common, gateway, graph, ioc_finder, settings, util
from ..common import (LoadContext, RecordField, RecordInstance, WhatRecord,
                      dataclass)
from ..shell import (LoadedIoc, ScriptContainer,
                     load_startup_scripts_with_metadata)
from .util import TaskHandler

TRUE_VALUES = {"1", "true", "True"}

logger = logging.getLogger(__name__)
_log_handler = None


class ServerLogHandler(logging.Handler):
    def __init__(self, message_count: int = 1000, level="DEBUG"):
        super().__init__(level=level)
        self.formatter = logging.Formatter(
            "%(asctime)s - PID %(process)d %(filename)18s: %(lineno)-3s "
            "%(funcName)-18s %(levelname)-8s %(message)s"
        )
        self.message_count = message_count
        self.messages = collections.deque(maxlen=message_count)

    def emit(self, record):
        self.messages.append(self.format(record))


@dataclasses.dataclass
class ServerPluginSpec:
    name: str
    #: Python module
    module: Optional[str] = None
    #: Or any executable
    executable: Optional[List[str]] = None
    #: Can be a dataclass or a builtin type
    # result_class: type
    files_to_monitor: List[str] = dataclasses.field(default_factory=list)
    results: Any = None

    async def update(self):
        if self.executable:
            script = " ".join(f'"{param}"' for param in self.executable)
        elif self.module:
            script = f'"{sys.executable}" -m {self.module}'
        else:
            raise ValueError("module and executable both unset")

        results = await util.run_script_with_json_output(script)
        results = results or {}
        files_to_monitor = results.get("files_to_monitor", None)
        if files_to_monitor:
            self.files_to_monitor = files_to_monitor
        if "record_to_metadata" not in results:
            raise ValueError(f"Invalid plugin output: {results}")

        self.results = results
        return results


class TooManyRecordsError(Exception):
    ...


def _compile_glob(glob_str, flags=re.IGNORECASE, separator="|"):
    return re.compile(
        "|".join(fnmatch.translate(glob_str) for part in glob_str.split(separator)),
        flags=flags,
    )


class ServerState:
    container: ScriptContainer
    pv_relations: Dict[
        str, DefaultDict[str, Tuple[RecordField, RecordField, Tuple[str, ...]]]
    ]
    archived_pvs: Set[str]
    gateway_config: gateway.GatewayConfig
    script_loaders: List[ioc_finder._IocInfoFinder]
    plugin_data: Dict[str, Any]

    def __init__(
        self,
        startup_scripts: List[str],
        script_loaders: List[str],
        standin_directories: Dict[str, str],
        gateway_config: Optional[str] = None,
        plugins: Optional[List[ServerPluginSpec]] = None,
    ):
        self.archived_pvs = set()
        self.container = ScriptContainer()
        self.gateway_config = None
        self.gateway_config_path = gateway_config
        self.plugin_data = {}
        self.plugins = plugins or []
        self.pv_relations = {}
        self.script_relations = {}
        self.standin_directories = standin_directories
        self.tasks = TaskHandler()
        self.script_loaders = [
            ioc_finder.IocScriptStaticList(startup_scripts)
        ] + [
            ioc_finder.IocScriptExternalLoader(loader)
            for loader in script_loaders
        ]

    async def async_init(self, app):
        self.tasks.create(self.update_from_script_loaders())
        self.tasks.create(self.update_plugins())

    async def update_from_script_loaders(self):
        startup_md = []
        for loader in self.script_loaders:
            await loader.update()
            for _, md in loader.scripts.items():
                startup_md.append(md)

        while True:
            logger.info("Checking for changed scripts and database files...")
            self._load_gateway_config()
            updated = [
                md for md in startup_md
                if not md.is_up_to_date()
            ]
            if not updated:
                logger.info("No changes found.")
                await asyncio.sleep(settings.SERVER_SCAN_PERIOD)
                continue

            logger.info(
                "%d IOC%s changed.", len(updated),
                " has" if len(updated) == 1 else "s have"
            )
            for idx, ioc in enumerate(updated[:10], 1):
                logger.info("* %d: %s", idx, ioc.name)
            if len(updated) > 10:
                logger.info("...")

            async for md, loaded in load_startup_scripts_with_metadata(
                *updated, standin_directories=self.standin_directories
            ):
                self.container.add_script(loaded)
                # Swap out the new loaded metadata
                idx = startup_md.index(md)
                startup_md.remove(md)
                startup_md.insert(idx, loaded.metadata)

            with common.time_context() as ctx:
                self.pv_relations = graph.build_database_relations(
                    self.container.database
                )
                self.script_relations = graph.build_script_relations(
                    self.container.database, self.pv_relations
                )
                logger.info("Updated PV/script relations in %.1f s", ctx())

            self.clear_cache()
            await asyncio.sleep(settings.SERVER_SCAN_PERIOD)

    async def update_plugins(self):
        for plugin in self.plugins:
            logger.info("Updating plugin: %s", plugin.name)
            with common.time_context() as ctx:
                try:
                    info = await plugin.update()
                except Exception:
                    logger.exception(
                        "Failed to update plugin %r [%.1f s]",
                        plugin.name, ctx()
                    )
                    continue
                else:
                    logger.info(
                        "Update plugin %r [%.1f s]",
                        plugin.name, ctx()
                    )

            for record, md in info["record_to_metadata"].items():
                ...
                # TODO update to not require annotation?

    def get_plugin_info(self) -> Dict[str, Any]:
        return {
            plugin.name: plugin.results
            for plugin in self.plugins
            if plugin.results
        }

    def _load_gateway_config(self):
        if not self.gateway_config_path:
            return

        if self.gateway_config is None:
            self.gateway_config = gateway.GatewayConfig(
                self.gateway_config_path
            )
        else:
            self.gateway_config.update_changed()

        for filename, pvlist in self.gateway_config.pvlists.items():
            if pvlist.hash is not None:
                self.container.loaded_files[str(filename)] = pvlist.hash

    def load_archived_pvs_from_file(self, filename):
        # TODO: could retrieve it at startup/periodically from the appliance
        with open(filename, "rt") as fp:
            self.archived_pvs = set(json.load(fp))

    def annotate_whatrec(self, whatrec: WhatRecord) -> WhatRecord:
        """
        Annotate WhatRecord instances with things ServerState knows about.
        """
        for instance in whatrec.instances:
            if not instance.is_pva:
                # For now, V3 only
                instance.metadata["archived"] = instance.name in self.archived_pvs
                instance.metadata["gateway"] = apischema.serialize(
                    self.get_gateway_info(instance.name)
                )
            for plugin in self.plugins:
                if not plugin.results:
                    continue

                instance_md = plugin.results["record_to_metadata"].get(
                    instance.name, None
                )
                if instance_md is not None:
                    instance.metadata[plugin.name] = instance_md

        return whatrec

    def whatrec(self, pvname) -> List[WhatRecord]:
        """Find WhatRecord matches."""
        return list(
            self.annotate_whatrec(rec)
            for rec in self.container.whatrec(pvname) or []
        )

    @property
    def database(self) -> Dict[str, RecordInstance]:
        """The CA/V3 Database of records."""
        return self.container.database

    @property
    def pva_database(self) -> Dict[str, RecordInstance]:
        """The pvAccess Database of groups/records."""
        return self.container.pva_database

    @functools.lru_cache(maxsize=2048)
    def get_graph(self, pv_names: Tuple[str], graph_type: str) -> graphviz.Digraph:
        if graph_type == "record":
            return self.get_link_graph(tuple(pv_names))
        if graph_type == "script":
            return self.get_script_graph(tuple(pv_names))
        raise RuntimeError("Invalid graph type")

    def get_script_graph(self, pv_names: Tuple[str]) -> graphviz.Digraph:
        if len(pv_names) > settings.MAX_RECORDS:
            raise TooManyRecordsError()

        if not pv_names:
            return graphviz.Digraph()
        _, _, digraph = graph.graph_script_relations(
            database=self.database,
            limit_to_records=pv_names,
            font_name="Courier",
            script_relations=self.script_relations,
        )
        return digraph

    def get_link_graph(self, pv_names: Tuple[str]) -> graphviz.Digraph:
        if len(pv_names) > settings.MAX_RECORDS:
            raise TooManyRecordsError()

        if not pv_names:
            return graphviz.Digraph()
        _, _, digraph = graph.graph_links(
            database=self.database,
            starting_records=pv_names,
            sort_fields=True,
            font_name="Courier",
            relations=self.pv_relations,
        )
        return digraph

    def clear_cache(self):
        for method in [
            self.get_gateway_info,
            self.get_matching_pvs,
            self.get_matching_iocs,
            self.get_graph_rendered,
        ]:
            method.cache_clear()

    @functools.lru_cache(maxsize=2048)
    def get_gateway_info(self, pvname: str) -> Optional[gateway.PVListMatches]:
        if self.gateway_config is None:
            return None
        return self.gateway_config.get_matches(pvname)

    @functools.lru_cache(maxsize=2048)
    def get_matching_pvs(self, glob_str: str) -> List[str]:
        regex = _compile_glob(glob_str)
        pv_names = set(self.database) | set(self.pva_database)
        return [pv_name for pv_name in sorted(pv_names) if regex.match(pv_name)]

    @functools.lru_cache(maxsize=2048)
    def get_matching_iocs(self, glob_str: str) -> List[LoadedIoc]:
        regex = _compile_glob(glob_str)
        return [
            loaded_ioc
            for script_path, loaded_ioc in sorted(self.container.scripts.items())
            if regex.match(script_path) or regex.match(loaded_ioc.metadata.name)
        ]

    @functools.lru_cache(maxsize=2048)
    def get_graph_rendered(
        self, pv_names: Tuple[str], format: str, graph_type: str
    ) -> bytes:
        graph = self.get_graph(pv_names, graph_type=graph_type)

        with tempfile.NamedTemporaryFile(suffix=f".{format}") as source_file:
            rendered_filename = graph.render(source_file.name, format=format)

        with open(rendered_filename, "rb") as fp:
            return fp.read()


@dataclass
class PVGetInfo:
    pv_name: str
    present: bool
    info: List[WhatRecord]

    _jinja_format_: ClassVar[Dict[str, str]] = {
        "console": """\
{{ pv_name }}:
    In database: {{ present }}
{% for _info in info %}
{% set item_info = render_object(_info, "console") %}
    {{ item_info | indent(4)}}
{% endfor %}
}
""",
    }


@dataclass
class PVGetMatchesResponse:
    glob: str
    matches: List[str]


@dataclass
class IocGetMatchesResponse:
    glob: str
    matches: List[common.IocMetadata]


AnyRecordInstance = Union[common.RecordInstanceSummary, common.RecordInstance]


@dataclass
class IocGetMatchingRecordsResponse:
    ioc_glob: str
    pv_glob: str
    # TODO: ew, redo this
    matches: List[Tuple[common.IocMetadata, List[AnyRecordInstance]]]


@dataclass
class FileLine:
    lineno: int
    line: str


class ServerHandler:
    routes = web.RouteTableDef()

    def __init__(self, state: ServerState):
        self.state = state

    async def async_init(self, app):
        await self.state.async_init(app)

    @routes.get("/api/pv/{pv_names}/info")
    async def api_pv_get_info(self, request: web.Request):
        pv_names = request.match_info.get("pv_names", "").split("|")
        info = {pv_name: self.state.whatrec(pv_name) for pv_name in pv_names}
        return web.json_response(
            apischema.serialize({
                pv_name: PVGetInfo(
                    pv_name=pv_name,
                    present=(pv_name in self.state.database or
                             pv_name in self.state.pva_database),
                    info=[obj for obj in info[pv_name]],
                )
                for pv_name in pv_names
            })
        )

    @routes.get("/api/pv/{glob_str}/matches")
    async def api_pv_get_matches(self, request: web.Request):
        max_matches = int(request.query.get("max", "200"))
        glob_str = request.match_info.get("glob_str", "*")
        matches = self.state.get_matching_pvs(glob_str)
        if max_matches > 0:
            matches = matches[:max_matches]

        return web.json_response(
            apischema.serialize(
                PVGetMatchesResponse(
                    glob=glob_str,
                    matches=matches,
                )
            )
        )

    @routes.get("/api/iocs/{glob_str}/matches")
    async def api_ioc_get_matches(self, request: web.Request):
        # Ignore max for now. This is not much in the way of information.
        # max_matches = int(request.query.get("max", "1000"))
        glob_str = request.match_info.get("glob_str", "*")
        match_metadata = [
            loaded_ioc.metadata
            for loaded_ioc in self.state.get_matching_iocs(glob_str)
        ]
        return web.json_response(
            apischema.serialize(
                IocGetMatchesResponse(
                    glob=glob_str,
                    matches=match_metadata,
                )
            )
        )

    @routes.get("/api/iocs/{ioc_glob}/pvs/{pv_glob}")
    async def api_ioc_get_pvs(self, request: web.Request):
        response = IocGetMatchingRecordsResponse(
            ioc_glob=request.match_info.get("ioc_glob", "*"),
            pv_glob=request.match_info.get("pv_glob", "*"),
            matches=[],
        )

        def get_all_records(shell_state):
            yield from shell_state.database.items()
            yield from shell_state.pva_database.items()

        pv_glob_re = _compile_glob(response.pv_glob)
        for loaded_ioc in self.state.get_matching_iocs(response.ioc_glob):
            record_matches = [
                rec_info.to_summary()
                for rec, rec_info in sorted(get_all_records(loaded_ioc.shell_state))
                if pv_glob_re.match(rec)
            ]
            if record_matches:
                response.matches.append((loaded_ioc.metadata, record_matches))

        return web.json_response(
            apischema.serialize(response)
        )

    # @routes.get("/api/graphql/query")
    # async def api_graphql_query(self, request: web.Request):
    # TODO: ...

    @routes.get("/api/plugin/info")
    async def api_plugin_info(self, request: web.Request):
        return web.json_response(self.state.get_plugin_info())

    @functools.lru_cache(maxsize=2048)
    def script_info_from_loaded_file(self, fn) -> common.IocshScript:
        assert fn in self.state.container.loaded_files

        with open(fn, "rt") as fp:
            lines = fp.read().splitlines()

        result = []
        for lineno, line in enumerate(lines, 1):
            result.append(
                common.IocshResult(
                    context=(LoadContext(fn, lineno),),
                    line=line,
                    outputs=[],
                    argv=None,
                    error=None,
                    redirects={},
                    result=None,
                )
            )
        return common.IocshScript(path=fn, lines=tuple(result))

    @routes.get("/api/file/info")
    async def api_ioc_info(self, request: web.Request):
        # script_name = pathlib.Path(request.query["file"])
        filename = request.query["file"]
        loaded_ioc = self.state.container.scripts.get(filename, None)
        if loaded_ioc:
            script_info = loaded_ioc.script
            ioc_md = loaded_ioc.metadata
        else:
            # Making this dual-purpose: script, db, or any loaded file
            ioc_md = None
            try:
                self.state.container.loaded_files[filename]
                script_info = self.script_info_from_loaded_file(filename)
            except KeyError as ex:
                raise web.HTTPBadRequest() from ex

        return web.json_response(
            apischema.serialize({
                "script": script_info,
                "ioc": ioc_md,
            })
        )

    async def get_graph(self, pv_names: List[str], use_glob: bool = False,
                        graph_type: str = "record",
                        format: str = "pdf"):
        if "*" in pv_names or use_glob:
            pv_names = self.state.get_matching_pvs(pv_names)
        else:
            pv_names = pv_names.split("|")

        if format == "dot":
            try:
                digraph = self.state.get_graph(
                    tuple(pv_names),
                    graph_type=graph_type
                )
            except TooManyRecordsError as ex:
                raise web.HTTPBadRequest() from ex

            return web.Response(
                content_type="text/vnd.graphviz",
                body=digraph.source,
            )

        rendered = self.state.get_graph_rendered(
            tuple(pv_names), format=format, graph_type=graph_type
        )
        try:
            content_type = {
                "pdf": "application/pdf",
                "png": "image/png",
                "svg": "image/svg+xml",
            }[format]
        except KeyError as ex:
            raise web.HTTPBadRequest() from ex

        return web.Response(
            content_type=content_type,
            body=rendered,
        )

    @routes.get("/api/logs/get")
    async def api_logs_get(self, request: web.Request):
        return web.json_response(
            list(_log_handler.messages)
        )

    @routes.get("/api/pv/{pv_names}/graph/{format}")
    async def api_pv_get_record_graph(self, request: web.Request):
        return await self.get_graph(
            pv_names=request.match_info["pv_names"],
            use_glob=request.query.get("glob", "false") in TRUE_VALUES,
            format=request.match_info["format"],
            graph_type="record",
        )

    @routes.get("/api/pv/{pv_names}/script-graph/{format}")
    async def api_pv_get_script_graph(self, request: web.Request):
        return await self.get_graph(
            pv_names=request.match_info["pv_names"],
            use_glob=request.query.get("glob", "false") in TRUE_VALUES,
            format=request.match_info["format"],
            graph_type="script",
        )


def add_routes(app: web.Application, handler: ServerHandler):
    routes = web.RouteTableDef()
    for route in handler.routes:
        if isinstance(route, web.StaticDef):
            routes.static(route.prefix, route.path, **route.kwargs)
        elif isinstance(route, web.RouteDef):
            method = getattr(handler, route.handler.__name__)
            routes.route(route.method, route.path, **route.kwargs)(method)
    app.router.add_routes(routes)
    return routes


def new_server(startup_scripts) -> web.Application:
    app = web.Application()
    handler = ServerHandler(startup_scripts)
    add_routes(app, handler)
    return app, handler


def run(*args, **kwargs):
    app, handler = new_server(*args, **kwargs)
    web.run_app(app)
    return app, handler


def configure_logging(loggers=None):
    global _log_handler
    _log_handler = ServerLogHandler()

    loggers = loggers or ["whatrecord"]
    for logger_name in loggers:
        logging.getLogger(logger_name).addHandler(_log_handler)


def main(
    scripts: Optional[List[str]] = None,
    script_loader: Optional[List[str]] = None,
    archive_file: Optional[str] = None,
    archive_viewer_url: Optional[str] = None,
    archive_management_url: Optional[str] = None,
    archive_update_period: int = 60,
    gateway_config: Optional[str] = None,
    port: int = 8898,
    standin_directory: Optional[Union[List, Dict]] = None,
):
    scripts = scripts or []
    script_loader = script_loader or []

    app = web.Application()

    standin_directory = standin_directory or {}
    if not isinstance(standin_directory, dict):
        standin_directory = dict(path.split("=", 1) for path in standin_directory)

    state = ServerState(
        startup_scripts=scripts,
        script_loaders=script_loader,
        standin_directories=standin_directory,
        # archive_viewer_url=archive_viewer_url,
        gateway_config=gateway_config,
        plugins=[
            ServerPluginSpec(
                name="happi",
                module="whatrecord.plugins.happi",
                executable=None,
                # result_class=dict,
            ),
        ],
    )

    handler = ServerHandler(state)

    add_routes(app, handler)

    if archive_file:
        handler.state.load_archived_pvs_from_file(archive_file)
    elif archive_management_url:
        ...
        # handler.set_archiver_url(archive_management_url)

    configure_logging()
    app.on_startup.append(handler.async_init)
    web.run_app(app, port=port)
    return app, handler


if __name__ == "__main__":
    app, handler = run(sys.argv[1:])
