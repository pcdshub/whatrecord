"""
TwinCAT / pytmc / blark whatrecord plugin

Match your TwinCAT project symbols to EPICS records.

Set ``project`` to generate metadata for one particular PLC project.

Alternatively, the plugin will query WHATRECORD_SERVER for all IOCs and attempt
to find ads-ioc-based IOCs with associated TwinCAT projects.

To annotate library-level information in dependencies (i.e., to let users "go
to the source code of dependency-library-sourced symbols"), be sure to
set ``BLARK_TWINCAT_ROOT`` per blark's documentation.
"""
from __future__ import annotations

import argparse
import asyncio
import dataclasses
import json
import logging
import pathlib
import re
import typing
from dataclasses import dataclass
from typing import Dict, Generator, Iterable, List, Optional, Tuple, cast

import apischema
import blark
import blark.dependency_store
import blark.summary
import pytmc.parser

from .. import cache, client, util
from ..common import AnyPath, FullLoadContext, IocMetadata, LoadContext
from ..server.common import PluginResults
from ..util import get_file_sha256, read_text_file_with_hash

logger = logging.getLogger(__name__)

# Stash the description for later usage by the CLI interface.
DESCRIPTION = __doc__.strip()


def _stringify_path(path: AnyPath) -> str:
    """Uniform strings from a pathlib.Path or string."""
    if isinstance(path, str):
        path = pathlib.Path(path)
    return str(path.resolve())


@dataclass
class TwincatPluginResults(PluginResults):
    def merge(self, results: TwincatPluginResults) -> None:
        self.files_to_monitor.update(results.files_to_monitor)
        self.record_to_metadata_keys.update(results.record_to_metadata_keys)
        self.metadata_by_key.update(results.metadata_by_key)
        self.execution_info.update(results.execution_info)
        if self.nested is not None:
            self.nested.update(results.nested or {})

    @classmethod
    def from_metadata(cls, md: PlcMetadata) -> TwincatPluginResults:
        plc_results = TwincatPluginResults(
            files_to_monitor={
                _stringify_path(path): shasum
                for path, shasum in md.loaded_files.items()
            },
            record_to_metadata_keys={
                rec: [sym] for rec, sym in md.record_to_symbol.items()
            },
            metadata_by_key=md.symbols,
            metadata={
                "dependencies": md.dependencies,
                "nc": md.nc,
            },
            execution_info={},
        )
        return TwincatPluginResults(
            nested={
                md.name: plc_results
            }
        )

    @classmethod
    def from_metadata_items(
        cls, mds: Iterable[PlcMetadata]
    ) -> TwincatPluginResults:
        results = None
        for plc_md in mds:
            single = TwincatPluginResults.from_metadata(plc_md)
            if results is None:
                results = single
            else:
                results.merge(single)

        if results is not None:
            return results

        return TwincatPluginResults(
            files_to_monitor={},
            record_to_metadata_keys={},
            metadata_by_key={},
            execution_info={"result": "No PLCs found."},
        )


@dataclass
class Declaration:
    context: FullLoadContext
    name: str = "unknown"
    type: str = "unknown"


@dataclass
class DataType:
    name: str


@dataclass
class PlcCode:
    ...


@dataclass
class NCAxis:
    """A single NC axis."""
    context: FullLoadContext
    filename: str
    hash: str

    axis_id: int
    name: str
    units: str
    params: Dict[str, str]

    @classmethod
    def from_pytmc(
        cls,
        axis: pytmc.parser.Axis,
    ) -> NCAxis:
        filename = str(axis.filename.resolve())
        return cls(
            context=(LoadContext(filename, 0), ),
            filename=filename,
            hash=get_file_sha256(filename),
            axis_id=axis.axis_number,
            name=axis.name,
            units=axis.units,
            params=dict(axis.summarize()),
        )


@dataclass
class NCAxes:
    """Top-level NC axis information."""
    context: FullLoadContext
    filename: pathlib.Path
    hash: str
    axes: List[NCAxis]

    @classmethod
    def from_pytmc(
        cls,
        project: pytmc.parser.TwincatItem,
        loaded_files: Optional[Dict[str, str]] = None,
    ) -> Optional[NCAxes]:
        """Create an NCAxes instance from a project filename."""
        try:
            nc: pytmc.parser.NC = next(project.root.find(pytmc.parser.NC))
        except StopIteration:
            return None

        nc_filename = _stringify_path(nc.filename)
        nc = cls(
            context=(LoadContext(nc_filename, 0), ),
            filename=nc.filename,
            hash=get_file_sha256(nc_filename),
            axes=[NCAxis.from_pytmc(axis) for axis in nc.axes],
        )

        if loaded_files is not None:
            loaded_files[_stringify_path(nc.filename)] = nc.hash
            for axis in nc.axes:
                loaded_files[_stringify_path(axis.filename)] = axis.hash

        return nc

    @classmethod
    def from_project_filename(
        cls,
        filename: pathlib.Path,
        loaded_files: Optional[Dict[str, str]] = None,
    ) -> Optional[NCAxes]:
        """Create an NCAxes instance from a project filename."""
        project = pytmc.parser.parse(filename)
        return cls.from_pytmc(project, loaded_files)


@dataclass
class PlcSymbolMetadata:
    context: FullLoadContext
    name: str
    type: str
    records: List[str]


@dataclass
class PlcMetadataCacheKey(cache.CacheKey):
    """
    These attributes define a PlcMetadata cache item.

    The PLC name and filename will be used as a cache key; however, additional
    checks will be made to see that the files have not changed on disk since
    the last save.
    """
    name: str
    filename: str
    include_dependencies: bool


def load_context_from_path(path: List[blark.summary.Summary]) -> FullLoadContext:
    """Get a FullLoadContext from a blark variable path."""
    result = []
    saw_files = set()
    for file, line in reversed(blark.summary.path_to_file_and_line(path)):
        file = str(file)
        if file not in saw_files:
            result.append(LoadContext(str(file), line))
            saw_files.add(file)

    return tuple(result[::-1])


def get_symbol_metadata(
    blark_md: blark.dependency_store.PlcMetadata,
    symbol: pytmc.parser.Symbol,
    require_records: bool = True,
    add_project_prefix: bool = True,
) -> Generator[PlcSymbolMetadata, None, None]:
    """Get symbol metadata given a pytmc Symbol."""
    symbol_type_name = symbol.data_type.qualified_type_name
    for pkg in pytmc.pragmas.record_packages_from_symbol(
        symbol,
        yield_exceptions=True,
        allow_no_pragma=False,
    ):
        if isinstance(pkg, Exception):
            # Eat these up rather than raising
            continue
        # context = get_symbol_context(symbol.data_type.name, pkg.tcname)
        path = blark_md.summary.find_path(pkg.tcname)
        if not path:
            # Can't find the declaration in the code, somehow
            continue

        records = [record.pvname for record in pkg.records]
        if records or not require_records:
            annotated_name = pkg.tcname
            if add_project_prefix:
                annotated_name = f"{blark_md.name}:{annotated_name}"

            try:
                chain_type_name = pkg.chain.data_type.qualified_type_name
            except AttributeError:
                chain_type_name = "unknown"

            if symbol_type_name == chain_type_name:
                type_name = symbol_type_name
            else:
                type_name = f"{chain_type_name} ({symbol_type_name})"

            yield PlcSymbolMetadata(
                context=load_context_from_path(path),
                name=annotated_name,
                records=records,
                type=type_name,
            )


@dataclass
class PytmcMetadata:
    tsproj: pytmc.parser.TcSmProject
    plcproj: pytmc.parser.PlcProject
    tmc: Optional[pytmc.parser.TcModuleClass] = None
    nc: Optional[NCAxes] = None

    @classmethod
    def from_tsproj(
        cls,
        tsproj: blark.solution.Project,
        plc_name: str,
        *,
        loaded_files: Optional[Dict[str, str]] = None,
    ) -> PytmcMetadata:
        if loaded_files is None:
            loaded_files = {}
        if tsproj.local_path is None:
            raise ValueError("Project without path")

        try:
            pytmc_tsproj = cast(
                pytmc.parser.TcSmProject,
                pytmc.parser.parse(tsproj.local_path)
            )
        except Exception as ex:
            raise ValueError(f"Failed to parse project: {tsproj.name}") from ex

        try:
            pytmc_plc = cast(
                pytmc.parser.PlcProject,
                pytmc_tsproj.plcs_by_name[plc_name]
            )
        except KeyError as ex:
            raise ValueError(f"Unable to find PLC project: {tsproj.name}") from ex

        md = cls(
            tsproj=pytmc_tsproj,
            plcproj=pytmc_plc,
            tmc=getattr(pytmc_plc, "tmc", None),
        )

        try:
            md.nc = NCAxes.from_pytmc(
                pytmc_tsproj,
                loaded_files=loaded_files,
            )
        except Exception:
            logger.exception(
                "Failed to load NC settings from project: %s",
                tsproj.local_path,
            )
        return md


@dataclass
class PlcMetadata(cache.InlineCached, PlcMetadataCacheKey):
    """This metadata is keyed on PlcMetadataCacheKey."""
    context: FullLoadContext
    symbols: Dict[str, PlcSymbolMetadata]
    loaded_files: Dict[str, str]
    record_to_symbol: Dict[str, str]
    # dependencies: Dict[str, blark.solution.DependencyInformation]
    # TODO
    dependencies: Dict[str, blark.dependency_store.DependencyVersion]
    blark_md: Optional[blark.dependency_store.PlcProjectMetadata] = dataclasses.field(
        default=None,
        metadata=apischema.metadata.skip
    )
    tsproj: Optional[blark.solution.Project] = dataclasses.field(
        default=None,
        metadata=apischema.metadata.skip
    )
    nc: Optional[NCAxes] = None

    @classmethod
    def from_ioc(
        cls,
        md: IocMetadata,
    ) -> Generator[PlcMetadata, None, None]:
        try:
            makefile_hash, makefile_contents, makefile_path = get_ioc_makefile(md)
        except FileNotFoundError:
            return

        project_info = get_project_from_ioc(md, makefile_contents)
        if project_info is None:
            logger.debug("No project found for %s", md.name)
            return

        loaded_files = {
            str(makefile_path): makefile_hash or get_file_sha256(makefile_path)
        }

        project, plc_name = project_info
        logger.info(
            "Found a PLC for this project: %s %s (%s)",
            md.name, plc_name, project
        )
        yield from PlcMetadata.from_project_filename(
            project,
            plc_whitelist=[plc_name],
            loaded_files=loaded_files,
        )

    @classmethod
    def from_blark(
        cls,
        blark_md: blark.dependency_store.PlcProjectMetadata,
        tsproj: blark.solution.Project,
        include_dependencies: bool = True,
        use_cache: bool = True,
    ) -> PlcMetadata:
        """Create a PlcMetadata instance from a pytmc-parsed one."""
        loaded_files = {
            _stringify_path(path): hash_
            for path, hash_ in blark_md.loaded_files.items()
        }

        pytmc_md = PytmcMetadata.from_tsproj(
            tsproj,
            plc_name=blark_md.name,
            loaded_files=loaded_files,
        )

        # TODO: blark - not capturing tsproj
        if tsproj.local_path is not None:
            loaded_files[_stringify_path(tsproj.local_path)] = get_file_sha256(
                tsproj.local_path
            )

        plc_fn = _stringify_path(blark_md.filename)
        if blark_md.plc is None or pytmc_md.tmc is None:
            logger.debug(
                "%s (%s): No TMC file for symbols; skipping...",
                plc_fn,
                blark_md.name,
            )
            return cls(
                name=blark_md.name,
                filename=plc_fn,
                include_dependencies=include_dependencies,
                context=(LoadContext(plc_fn, 0), ),
                dependencies=blark_md.dependencies,
                symbols={},
                record_to_symbol={},
                nc=None,
                loaded_files=loaded_files,
                tsproj=tsproj,
                blark_md=blark_md,
            )

        if use_cache:
            key = PlcMetadataCacheKey(
                name=blark_md.name,
                filename=plc_fn,
                include_dependencies=include_dependencies,
            )
            cached = cls.from_cache(key)
            if cached is not None:
                if util.check_files_up_to_date(cached.loaded_files):
                    return cached

        loaded_files[plc_fn] = util.get_file_sha256(plc_fn)

        md = cls(
            name=blark_md.plc.name or blark_md.name,
            filename=plc_fn,
            include_dependencies=include_dependencies,
            context=(LoadContext(plc_fn, 0), ),
            symbols={},
            record_to_symbol={},
            dependencies=blark_md.dependencies,
            loaded_files=loaded_files,
            nc=pytmc_md.nc,
            tsproj=tsproj,
            blark_md=blark_md,
        )

        def by_name(symbol):
            return symbol.name

        tmc = pytmc_md.tmc
        for symbol in sorted(pytmc.pragmas.find_pytmc_symbols(tmc), key=by_name):
            for symbol_md in get_symbol_metadata(blark_md, symbol):
                md.symbols[symbol_md.name] = symbol_md
                for record in symbol_md.records:
                    md.record_to_symbol[record] = symbol_md.name

        logger.debug(
            "PLC %s: Found %d symbols which generated metadata -> %d records",
            blark_md.plc.name,
            len(md.symbols),
            len(md.record_to_symbol),
        )
        if use_cache:
            md.save_to_cache()

        return md

    @classmethod
    def from_project_filename(
        cls,
        project: AnyPath,
        include_dependencies: bool = True,
        plc_whitelist: Optional[List[str]] = None,
        loaded_files: Optional[Dict[str, str]] = None,
        use_cache: bool = True,
    ) -> Generator[PlcMetadata, None, None]:
        """Given a project/solution filename, get all PlcMetadata."""
        if loaded_files is None:
            loaded_files = {}
        solution = blark.solution.make_solution_from_files(project)
        logger.debug(
            "Solution path %s projects %s", solution.filename, solution.projects
        )
        for tsproj_project in solution.projects:
            logger.debug("Found tsproj %s", tsproj_project.name)
            try:
                parsed_tsproj = tsproj_project.load()
            except Exception:
                logger.exception("Failed to load project %s", tsproj_project.name)
                continue

            for plc_name, plc in parsed_tsproj.plcs_by_name.items():
                if plc_whitelist and plc_name not in plc_whitelist:
                    continue

                logger.debug("Found PLC project %s", plc_name)
                plc_md = blark.dependency_store.PlcProjectMetadata.from_plcproject(
                    plc,
                    include_dependencies=include_dependencies,
                )
                if plc_md is None:
                    continue

                logger.debug(
                    "tsproj %s: Found plc project %s from %s",
                    tsproj_project.name,
                    plc_md.name,
                    plc_md.filename,
                )
                yield cls.from_blark(
                    blark_md=plc_md,
                    tsproj=tsproj_project,
                    include_dependencies=include_dependencies,
                    use_cache=use_cache,
                )


MAKEFILE_VAR_RE = re.compile(r"^([A-Z_][A-Z0-9_]+)\s*:?=\s*(.*)$", re.IGNORECASE | re.MULTILINE)


def get_ioc_makefile(md: IocMetadata) -> Tuple[str, str, pathlib.Path]:
    """Get the IOC Makefile contents, if available."""
    makefile_path = (md.script.parent / "Makefile").resolve()
    sha, contents = read_text_file_with_hash(makefile_path)
    return sha, contents, makefile_path


def get_project_from_ioc(md: IocMetadata, makefile: str) -> Optional[Tuple[pathlib.Path, str]]:
    """Get the TwinCAT Project from a provided ads-ioc IocMetadata and Makefile contents."""
    variables = dict(MAKEFILE_VAR_RE.findall(makefile))
    logger.debug("IOC: %s Makefile variables: %s", md.name, variables)
    try:
        plc_name = variables["PLC"]
        project_path = variables["PROJECT_PATH"]
    except KeyError:
        return None

    project_path = (md.script.parent / project_path).resolve()
    if not project_path.exists():
        logger.debug("Project path doesn't exist: %s", project_path)
        return

    return project_path, plc_name


async def main(
    project: str,
    server: Optional[str] = None,
    pretty: bool = False,
    verbose: bool = False,
) -> List[PlcMetadata]:
    if verbose:
        logging.basicConfig(level="DEBUG")
        logging.getLogger("parso").setLevel("WARNING")

    if project is not None:
        return list(PlcMetadata.from_project_filename(project))

    results = []
    ioc_info = await client.get_iocs(server=server)
    for md in ioc_info.matches:
        try:
            for plc_md in PlcMetadata.from_ioc(md):
                results.append(plc_md)
        except Exception:
            logger.exception("Failed to add PLC from makefile: %s", md.name)
    return results


async def _cli_main():
    parser = _get_argparser()
    args = parser.parse_args()
    results = await main(**vars(args))
    whatrecord_results = TwincatPluginResults.from_metadata_items(results)
    json_results = apischema.serialize(whatrecord_results)
    dump_args = {"indent": 4} if args.pretty else {}
    print(json.dumps(json_results, sort_keys=True, **dump_args))


def _get_argparser(parser: typing.Optional[argparse.ArgumentParser] = None):
    if parser is None:
        parser = argparse.ArgumentParser(description=DESCRIPTION)

    parser.add_argument(
        "project",
        nargs="?",
        help="TwinCAT Project to parse"
    )
    parser.add_argument(
        "--server", help="WhatRecord API server URL"
    )
    parser.add_argument(
        "-p", "--pretty", action="store_true", help="Pretty JSON output"
    )
    parser.add_argument(
        "-v", "--verbose", action="store_true", help="Verbose logging"
    )
    return parser


if __name__ == "__main__":
    results = asyncio.run(_cli_main())
