import fnmatch
import functools
import json
import os
import re
import sys
import tempfile
from typing import DefaultDict, Dict, List, Optional, Set, Tuple, Union

import apischema
import graphviz
from aiohttp import web

from .. import common, gateway, graph
from ..common import RecordField, WhatRecord, dataclass
from ..shell import ScriptContainer, load_startup_scripts

# from . import html as html_mod
# from . import static

# STATIC_PATH = pathlib.Path(static.__file__).parent
# HTML_PATH = pathlib.Path(html_mod.__file__).parent
TRUE_VALUES = {"1", "true", "True"}
MAX_RECORDS = int(os.environ.get("WHATRECORD_MAX_RECORDS", 200))

# aiohttp_jinja2.setup(
#     app,
#     loader=jinja2.FileSystemLoader('/path/to/templates/folder')
# )


class TooManyRecordsError(Exception):
    ...


class ServerState:
    container: ScriptContainer
    pv_relations: Dict[
        str, DefaultDict[str, Tuple[RecordField, RecordField, Tuple[str, ...]]]
    ]
    archived_pvs: Set[str]
    gateway_config: gateway.GatewayConfig

    def __init__(
        self,
        startup_scripts: List[str],
        script_loaders: List[str],
        standin_directories: Dict[str, str]
    ):
        self.standin_directories = standin_directories
        self.container = load_startup_scripts(
            *startup_scripts, standin_directories=standin_directories
        )
        self.pv_relations = graph.build_database_relations(self.container.database)
        self.script_relations = graph.build_script_relations(
            self.container.database, self.pv_relations)
        self.archived_pvs = set()
        self.gateway_config = None

    def load_gateway_config(self, path):
        self.gateway_config = gateway.GatewayConfig(path)
        for config in self.gateway_config.filenames:
            config = str(config)
            self.container.loaded_files[config] = config

    def load_archived_pvs_from_file(self, filename):
        # TODO: could retrieve it at startup/periodically from the appliance
        with open(filename, "rt") as fp:
            self.archived_pvs = set(json.load(fp))

    def whatrec(self, pvname):
        def annotate(rec: WhatRecord):
            rec.instance.metadata["archived"] = rec.instance.name in self.archived_pvs
            rec.instance.metadata["gateway"] = self.get_gateway_info(rec.instance.name)
            return rec

        return list(annotate(rec) for rec in self.container.whatrec(pvname) or [])

    @property
    def database(self):
        return self.container.database

    @functools.lru_cache(maxsize=2048)
    def get_graph(self, pv_names: Tuple[str], graph_type: str) -> graphviz.Digraph:
        if graph_type == "record":
            return self.get_link_graph(tuple(pv_names))
        if graph_type == "script":
            return self.get_script_graph(tuple(pv_names))
        raise RuntimeError("Invalid graph type")

    def get_script_graph(self, pv_names: Tuple[str]) -> graphviz.Digraph:
        if len(pv_names) > MAX_RECORDS:
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
        if len(pv_names) > MAX_RECORDS:
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

    @functools.lru_cache(maxsize=2048)
    def get_gateway_info(self, pvname: str) -> Optional[gateway.PVListMatches]:
        if self.gateway_config is None:
            return None
        return self.gateway_config.get_matches(pvname)

    @functools.lru_cache(maxsize=2048)
    def get_matching_pvs(self, glob_str: str) -> List[str]:
        regex = re.compile(
            "|".join(fnmatch.translate(glob_str) for part in glob_str.split("|")),
            flags=re.IGNORECASE,
        )
        return [pv_name for pv_name in sorted(self.database) if regex.match(pv_name)]

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


@dataclass
class PVGetMatchesResponse:
    glob: str
    matching_pvs: List[str]


@dataclass
class FileLine:
    lineno: int
    line: str


class ServerHandler:
    routes = web.RouteTableDef()

    def __init__(
        self,
        startup_scripts: List[str],
        script_loader: List[str],
        standin_directories: Dict[str, str],
        archive_viewer_url: Optional[str] = None
    ):
        self.state = ServerState(
            startup_scripts, script_loader, standin_directories
        )
        self.archive_viewer_url = None

    @routes.get("/api/pv/{pv_names}/info")
    async def api_pv_get_info(self, request: web.Request):
        pv_names = request.match_info.get("pv_names", "").split("|")
        info = {pv_name: self.state.whatrec(pv_name) for pv_name in pv_names}
        return web.json_response(
            apischema.serialize({
                pv_name: PVGetInfo(
                    pv_name=pv_name,
                    present=pv_name in self.state.database,
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
                    matching_pvs=matches,
                )
            )
        )

    @functools.lru_cache(maxsize=2048)
    def script_info_from_loaded_file(self, fn) -> common.IocshScript:
        assert fn in self.state.container.loaded_files

        with open(fn, "rt") as fp:
            lines = fp.read().splitlines()

        context = common.LoadContext(fn, 0)
        result = []
        for lineno, line in enumerate(lines, 1):
            context.line = lineno
            result.append(
                common.IocshResult(
                    context=(context.freeze(),),
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
            return web.json_response(apischema.serialize(loaded_ioc.script))

        # Making this dual-purpose: script, db, or any loaded file
        try:
            self.state.container.loaded_files[filename]
            script_info = self.script_info_from_loaded_file(filename)
        except KeyError as ex:
            raise web.HTTPBadRequest() from ex

        return web.json_response(apischema.serialize(script_info))

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

    # # TODO: these will go away when not in development mode
    # @routes.get("/index.html")
    # @routes.get("/")
    # async def index_page(self, request: web.Request):
    #     return web.FileResponse(HTML_PATH / "index.html")

    # @routes.get("/file")
    # @routes.get("/whatrec")
    # async def misc_page(self, request: web.Request):
    #     fn = request.path.split("/")[-1]
    #     return web.FileResponse(HTML_PATH / (fn + ".html"))

    # routes.static("/_static", STATIC_PATH, show_index=False)


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


def main(
    scripts: Optional[List[str]] = None,
    script_loader: Optional[List[str]] = None,
    archive_file: Optional[str] = None,
    archive_viewer_url: Optional[str] = None,
    archive_management_url: Optional[str] = None,
    archive_update_period: int = 60,
    gateway_config: Optional[str] = None,
    port: int = 8899,
    standin_directory: Optional[Union[List, Dict]] = None,
):
    scripts = scripts or []
    script_loader = script_loader or []

    app = web.Application()

    standin_directory = standin_directory or {}
    if not isinstance(standin_directory, dict):
        standin_directory = dict(path.split("=", 1) for path in standin_directory)

    handler = ServerHandler(
        scripts,
        script_loader,
        standin_directories=standin_directory,
        archive_viewer_url=archive_viewer_url
    )
    add_routes(app, handler)

    if archive_file:
        handler.state.load_archived_pvs_from_file(archive_file)
    elif archive_management_url:
        ...
        # handler.set_archiver_url(archive_management_url)

    if gateway_config:
        handler.state.load_gateway_config(gateway_config)

    web.run_app(app, port=port)
    return app, handler


if __name__ == "__main__":
    app, handler = run(sys.argv[1:])
