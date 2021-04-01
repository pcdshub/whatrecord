import dataclasses
import fnmatch
import functools
import json
import os
import pathlib
import re
import sys
import tempfile
from typing import List, Optional, Sequence, Tuple

import graphviz
from aiohttp import web

from .. import graph
from ..common import WhatRecord
from ..db import split_record_and_field
from ..shell import load_multiple_startup_scripts
from . import html as html_mod
from . import static

STATIC_PATH = pathlib.Path(static.__file__).parent
HTML_PATH = pathlib.Path(html_mod.__file__).parent
TRUE_VALUES = {"1", "true", "True"}
MAX_RECORDS = int(os.environ.get("WHATRECORD_MAX_RECORDS", 200))

# aiohttp_jinja2.setup(
#     app,
#     loader=jinja2.FileSystemLoader('/path/to/templates/folder')
# )


class TooManyRecordsError(Exception):
    ...


class ServerState:
    def __init__(self, startup_scripts):
        self.container = load_multiple_startup_scripts(*startup_scripts)
        self.pv_relations = graph.build_database_relations(self.container.database)
        self.archived_pvs = set()

    def load_archived_pvs_from_file(self, filename):
        # TODO: could retrieve it at startup/periodically from the appliance
        with open(filename, "rt") as fp:
            self.archived_pvs = set(json.load(fp))

    def whatrec(self, pvname):
        def annotate(rec: WhatRecord):
            rec.instance.archived = rec.instance.name in self.archived_pvs
            return rec

        return list(annotate(rec) for rec in self.container.whatrec(pvname) or [])

    @property
    def database(self):
        return self.container.database

    @functools.lru_cache(maxsize=2048)
    def get_graph(self, pv_names: Sequence[str]) -> graphviz.Digraph:
        if len(pv_names) > MAX_RECORDS:
            raise TooManyRecordsError()

        pv_names = tuple(pv_names)
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
    def get_matching_pvs(self, glob_str: str) -> Tuple[str, ...]:
        regex = re.compile(
            "|".join(fnmatch.translate(glob_str) for part in glob_str.split("|")),
            flags=re.IGNORECASE,
        )
        return tuple(
            pv_name for pv_name in sorted(self.database) if regex.match(pv_name)
        )

    @functools.lru_cache(maxsize=2048)
    def get_graph_rendered(self, pv_names: Sequence[str], format: str) -> bytes:
        graph = self.get_graph(pv_names)
        with tempfile.NamedTemporaryFile(suffix=f".{format}") as source_file:
            rendered_filename = graph.render(source_file.name, format=format)

        with open(rendered_filename, "rb") as fp:
            return fp.read()


class ServerHandler:
    routes = web.RouteTableDef()

    def __init__(self, startup_scripts):
        self.state = ServerState(startup_scripts)

    @routes.get("/api/pv/{pv_names}/info")
    async def api_pv_get_info(self, request: web.Request):
        pv_names = request.match_info.get("pv_names", "").split("|")
        info = {
            pv_name: self.state.whatrec(pv_name) for pv_name in pv_names
        }
        response = {
            pv_name: {
                "pv_name": pv_name,
                "present": pv_name in self.state.database,
                "archived": split_record_and_field(pv_name)[0]
                in self.state.archived_pvs,
                "info": [dataclasses.asdict(obj) for obj in info[pv_name]],
            }
            for pv_name in pv_names
        }

        return web.json_response(response)

    @routes.get("/api/pv/{glob_str}/matches")
    async def api_pv_get_matches(self, request: web.Request):
        max_matches = int(request.query.get("max", "200"))
        glob_str = request.match_info.get("glob_str", "*")
        matches = self.state.get_matching_pvs(glob_str)
        if max_matches > 0:
            matches = matches[:max_matches]

        return web.json_response(
            dict(
                glob=glob_str,
                matching_pvs=matches,
            )
        )

    @routes.get("/api/database/get")
    async def api_db_get(self, request: web.Request):
        try:
            # Only allow reading files we've scanned before
            fn = pathlib.Path(request.query["filename"])
            self.state.container.loaded_files[fn]
        except KeyError as ex:
            raise web.HTTPBadRequest() from ex

        with open(fn, "rt") as fp:
            return web.json_response(
                [
                    dict(lineno=lineno, line=line)
                    for lineno, line in enumerate(fp.read().splitlines(), 1)
                ]
            )

    @routes.get("/api/script/info")
    async def api_ioc_info(self, request: web.Request):
        try:
            script_info = self.state.container.scripts[request.query["script"]]
        except KeyError as ex:
            raise web.HTTPBadRequest() from ex

        return web.json_response(dataclasses.asdict(script_info))

    @routes.get("/api/pv/{pv_names}/graph/{format}")
    async def api_pv_get_graph(self, request: web.Request):
        pv_names = request.match_info["pv_names"]
        if "*" in pv_names or request.query.get("glob", "false") in TRUE_VALUES:
            pv_names = self.state.get_matching_pvs(pv_names)
        else:
            pv_names = tuple(pv_names.split("|"))

        try:
            digraph = self.state.get_graph(pv_names)
        except TooManyRecordsError as ex:
            raise web.HTTPBadRequest() from ex

        format = request.match_info.get("format", "pdf")
        if format == "dot":
            return web.json_response(
                dict(
                    pv_names=pv_names,
                    dot_source=digraph.source,
                )
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
            body=self.state.get_graph_rendered(pv_names, format=format),
        )

    # TODO: these will go away when not in development mode
    @routes.get("/index.html")
    @routes.get("/")
    async def index_page(self, request: web.Request):
        return web.FileResponse(HTML_PATH / "index.html")

    @routes.get("/script")
    @routes.get("/whatrec")
    @routes.get("/database")
    async def misc_page(self, request: web.Request):
        fn = request.path.split("/")[-1]
        return web.FileResponse(HTML_PATH / (fn + ".html"))

    routes.static("/_static", STATIC_PATH, show_index=False)


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
    scripts: List[str],
    archive_file: Optional[str] = None,
    archive_management_url: Optional[str] = None,
    archive_update_period: int = 60,
):
    app = web.Application()
    handler = ServerHandler(scripts)
    add_routes(app, handler)

    if archive_file:
        handler.state.load_archived_pvs_from_file(archive_file)
    elif archive_management_url:
        ...
        # handler.set_archiver_url(archive_management_url)

    web.run_app(app)
    return app, handler


if __name__ == "__main__":
    app, handler = run(sys.argv[1:])
