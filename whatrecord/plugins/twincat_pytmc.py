"""
TwinCAT / pytmc whatrecord plugin

Match your TwinCAT project symbols to EPICS records.
"""
from __future__ import annotations

import argparse
import collections
import distutils.version
import functools
import json
import logging
import pathlib
import re
import typing
from dataclasses import dataclass, field
from typing import Any, Dict, Generator, Iterable, List, Optional, Tuple

import apischema
import blark
import blark.parse
import lark
import pytmc
import pytmc.code

from .. import settings, transformer
from ..common import FullLoadContext, LoadContext
from ..server.common import PluginResults

# from ..util import get_file_sha256
# from .util import suppress_output_decorator

logger = logging.getLogger(__name__)

# Stash the description for later usage by the CLI interface.
DESCRIPTION = __doc__.strip()


def get_tsprojects_from_filename(filename):
    """
    From a TwinCAT solution (.sln) or .tsproj, return all tsproj projects.

    Returns
    -------
    root : pathlib.Path
        Project root directory (where the solution or provided tsproj is
        located).

    projects : list
        List of tsproj projects.
    """
    filename = pathlib.Path(filename).resolve()
    if filename.suffix == '.tsproj':
        return filename.parent, [filename]
    if filename.suffix == '.sln':
        return filename.parent, pytmc.parser.projects_from_solution(filename)

    raise RuntimeError(f'Expected a .tsproj/.sln file; got {filename.suffix!r}')


def code_between(
    text: str,
    start_marker: re.Pattern,
    end_marker: re.Pattern,
    *,
    include_markers: bool = True
) -> Tuple[Optional[int], str]:
    '''
    From a block of text, return all lines between `start_marker` and
    `end_marker`.

    Parameters
    ----------
    text : str
        The block of text.
    start_marker : re.Pattern
        The block-starting marker to match.
    end_marker : re.Pattern
        The block-ending marker to match.
    include_markers : bool, optional
        Include marker lines as well.

    Returns
    -------
    lineno : int
        The first line number.

    code: str
        The code.
    '''
    found_start = False
    # TODO: check if in comment section... big todo... yeah
    result = []
    first_line = None
    for lineno, line in enumerate(text.splitlines(), 1):
        if not found_start:
            if start_marker.fullmatch(line.strip()):
                if include_markers:
                    result.append(line)
                first_line = lineno
                found_start = True
        elif found_start:
            if end_marker.fullmatch(line.strip()):
                if include_markers:
                    result.append(line)
                break
            result.append(line)

    return first_line, "\n".join(result)


VARIABLE_BLOCKS = {
    section: (re.compile(start, re.IGNORECASE), re.compile(end, re.IGNORECASE))
    for section, start, end in (
        ("type", r"TYPE\s.*", "END_TYPE"),
        ("var", "VAR", "END_VAR"),
        ("input", "VAR_INPUT", "END_VAR"),
        ("output", "VAR_OUTPUT", "END_VAR"),
        ("inout", "VAR_IN_OUT", "END_VAR"),
        ("constant", r"VAR\s*CONSTANT", "END_VAR"),
        ("persistent", r"VAR\s*PERSISTENT", "END_VAR"),
        ("global", r"VAR_GLOBAL", "END_VAR"),
    )
}


def get_declarations_code_from_source(source: str) -> Tuple[str, int, str]:
    """
    Get declaration code given source.

    Yields
    ------
    name : str
        The declaration block type.

    lineno : int
        The line number the code starts on.

    code : str
        The declaration code itself.
    """
    for name, (start_marker, end_marker) in VARIABLE_BLOCKS.items():
        lineno, code = code_between(
            source,
            start_marker=start_marker,
            end_marker=end_marker,
            include_markers=True,
        )
        if lineno is not None:
            yield name, lineno, code


@dataclass
class PytmcPluginResults(PluginResults):
    # Could potentially further specify metadata_by_key or metadata

    def merge(self, results: PytmcPluginResults) -> None:
        self.files_to_monitor.update(results.files_to_monitor)
        self.record_to_metadata_keys.update(results.record_to_metadata_keys)
        self.metadata_by_key.update(results.metadata_by_key)
        self.execution_info.update(results.execution_info)

    @classmethod
    def from_metadata(cls, md: PlcMetadata) -> PytmcPluginResults:
        return PytmcPluginResults(
            files_to_monitor={},
            record_to_metadata_keys={
                rec: [sym] for rec, sym in md.record_to_symbol.items()
            },
            metadata_by_key=md.symbols,
            metadata=None,
            execution_info={},
        )

    @classmethod
    def from_metadata_items(
        cls, mds: Iterable[PlcMetadata]
    ) -> Optional[PytmcPluginResults]:
        results = None
        for plc_md in mds:
            single = PytmcPluginResults.from_metadata(plc_md)
            if results is None:
                results = single
            else:
                results.merge(single)
        return results


@dataclass
class Declaration:
    context: FullLoadContext = field(default_factory=tuple)
    name: str = "unknown"
    type: str = "unknown"


@dataclass
class DataType:
    name: str


@dataclass
class PlcCode:
    name: str
    context: FullLoadContext
    declarations: Dict[str, Declaration]

    @classmethod
    def from_pytmc(cls, code_obj: pytmc.parser.TwincatItem) -> PlcCode:
        """Parse out declarations and context information from the Plc code object."""
        md_declarations = {}
        decl_source_items = get_declarations_code_from_source(
            code_obj.get_source_code()
        )

        for var_section, lineno, decl_source in decl_source_items:
            logger.debug(
                "Parsing declarations from %s code=%r",
                code_obj.filename, code_obj.name
            )
            decl_dict = parse_declarations(
                var_section,
                code_obj.filename,
                code_obj.name,
                decl_source,
                line_number=lineno,
            )
            decl_dict.pop("unknown", None)
            for key, value in decl_dict.items():
                md_declarations[key] = value
                logger.debug(f"-> {key} = {value.type} {value.context[0].line}")

        return cls(
            name=str(code_obj.name),
            context=(LoadContext(str(code_obj.filename), 0), ),
            declarations=md_declarations,
        )

    @classmethod
    def from_pytmc_plc(
        cls, plc: pytmc.parser.Plc
    ) -> Generator[PlcCode, None, None]:
        """Parse all code from a given Plc."""
        code_sections = [
            ("POUs", plc.pou_by_name),
            ("GVLs", plc.gvl_by_name),
            ("DUTs", plc.dut_by_name),
        ]

        for _, section_dict in code_sections:
            for _, code_obj in section_dict.items():
                yield cls.from_pytmc(code_obj)


def _find_in_items(items, cls):
    """Find ``cls`` in Transformer item tuple/tree/etc."""
    if isinstance(items, tuple):
        for item in items:
            dt = _find_in_items(item, cls)
            if dt is not None:
                return dt
    elif isinstance(items, lark.Tree):
        for item in items.children:
            dt = _find_in_items(item, cls)
            if dt is not None:
                return dt
    elif isinstance(items, cls):
        return items


@lark.visitors.v_args(inline=True)
class _DeclarationsTransformer(lark.Transformer):
    """
    Transform tokenized PLC source code into a declarations dictionary.

    Parameters
    -----------
    filename : str
        The filename of the source code.

    line_number_offset : int
        An offset applied to lark Token line numbers for LoadContext.
    """
    # NOTE: This could use a lot of reworking. blark's grammar is really a
    # work-in-progress.  I'm just figuring out what to do with it and how to
    # work with it.
    # This is in fact only working with small portions of PLC code at the
    # moment - limiting to just the declarations blocks.  It's also very
    # reductive, in that it throws away a lot of useful information.
    # This may get scrapped or reworked entirely.
    # TODO: EXTENDS not supported yet

    declarations: Dict[str, Declaration]
    filename: str
    line_number_offset: int
    pragmas: List[str]

    def __init__(self, filename: str, visit_tokens=False, line_number_offset: int = 0):
        super().__init__(visit_tokens=visit_tokens)
        self.declarations = {}
        self.filename = filename
        self.line_number_offset = line_number_offset
        self.pragmas = []

    start = transformer.ignore
    iec_source = transformer.ignore
    global_var_name = transformer.pass_through
    structure_type_name = transformer.pass_through
    structure_element_name = transformer.pass_through
    structure_element_initialization = transformer.tuple_args

    # def __default__(self, *args):
    #     return super().__default__(*args)

    def _type_name(self, type_, *_):
        if isinstance(type_, DataType):
            # I am lazy
            return type_
        return DataType(str(type_))

    # These all have a single "type" argument:
    array_spec_type_name = _type_name
    array_type_name = _type_name
    bit_string_type_name = _type_name
    data_type_name = _type_name
    date_type_name = _type_name
    derived_type_name = _type_name
    dotted_name = _type_name
    elementary_type_name = _type_name
    enum_data_type_name = _type_name
    enumerated_type_name = _type_name
    generic_type_name = _type_name
    integer_type_name = _type_name
    real_type_name = _type_name
    simple_specification = _type_name
    simple_type_name = _type_name
    single_element_type_name = _type_name
    string_type_name = _type_name
    structure_type_name = _type_name
    subrange_type_name = _type_name
    # non_generic_type_name = _type_name

    # These have extra args that we throw away:
    string_type = _type_name  # Used in structure elements, STRING/WSTRING
    string_var_type = _type_name
    single_byte_string_spec = _type_name
    double_byte_string_spec = _type_name

    def _get_context(self, token: lark.Token) -> FullLoadContext:
        """Get a full load context from a given lark Token."""
        ctx = LoadContext(
            name=self.filename,
            line=token.line + self.line_number_offset
        )
        return (ctx, )

    def _variable_name(self, name):
        return Declaration(
            context=self._get_context(name),
            name=str(name),
        )

    structure_element_name = _variable_name
    variable_name = _variable_name

    expression = transformer.tuple_args
    single_byte_character_string = transformer.stringify
    double_byte_character_string = transformer.stringify

    exponent = transformer.stringify
    real_literal = transformer.stringify
    boolean_literal = transformer.stringify
    hex_integer = transformer.stringify
    octal_integer = transformer.stringify
    bit = transformer.stringify
    single_byte_character_representation = transformer.stringify
    double_byte_character_representation = transformer.stringify
    common_character_representation = transformer.stringify
    integer_literal = transformer.tuple_args

    located_var_spec_init = transformer.tuple_args

    global_var_list = transformer.tuple_args
    global_var_declarations = transformer.tuple_args
    global_var_spec = transformer.pass_through
    global_var_spec_location = transformer.tuple_args

    def simple_spec_init(self, *items):
        return items

    def global_var_decl(self, names, *info):
        if isinstance(names, str):
            names = [names]
        declarations = []
        dtype = _find_in_items(info, DataType)
        for name in names:
            decl = Declaration(
                context=self._get_context(name),
                name=str(name),
                type=dtype.name if dtype else "unknown",
            )
            declarations.append(decl)
            if decl.name != "unknown" and decl.type != "unknown":
                self.declarations[name] = decl
        return declarations

    def var_init_decl(self, *info):
        decl = _find_in_items(info, Declaration)
        if decl and decl.name != "unknown" and decl.type != "unknown":
            self.declarations[decl.name] = decl
            return decl

        dtype = _find_in_items(info, DataType)
        res = Declaration(
            context=decl.context if decl else None,
            name=decl.name if decl else "unknown",
            type=dtype.name if dtype else "unknown",
        )
        if not (decl and dtype):
            raise RuntimeError(
                f"Missing declaration name or type; "
                f"some more grammar/transformer work to do ({res})"
            )
        self.declarations[res.name] = res
        return res

    structure_element_declaration = var_init_decl
    fb_decl = var_init_decl
    fb_invocation_decl = var_init_decl

    def fb_decl_name_list(self, *names):
        return tuple(
            Declaration(
                context=self._get_context(name),
                name=str(name),
            )
            for name in names
        )

    fb_name = transformer.pass_through
    fb_invocation_name = _type_name

    structure_initialize = transformer.pass_through
    structure_initialization = transformer.tuple_args
    function_block_declaration = transformer.tuple_args
    initialized_structure = transformer.tuple_args

    def pragma(self, pragma):
        self.pragmas.append(str(pragma))


def parse_declarations(
    var_section: str,
    filename: pathlib.Path,
    code_name: str,
    decl_source: str,
    *,
    line_number: int = 1
) -> Dict[str, Declaration]:

    line_offset = line_number - 1
    # line 1 will be (line_offset + 1) = line_number
    try:
        # TODO better handling of sections than taking a look at the start
        if var_section == "global":
            # Standalone section
            # TODO blark grammar bug in GVLs but not FBs?
            source = decl_source.replace("FB_Arbiter(1)", "FB_Arbiter")
        elif var_section == "type":
            # Standalone type section
            source = decl_source
        else:
            source = (
                f"FUNCTION_BLOCK {code_name}\n"
                f"{decl_source}\n"
                f"END_FUNCTION_BLOCK"
            )
            line_offset -= 1  # Addition of FUNCTION_BLOCK
        parsed = blark.parse.parse_source_code(source)
    except Exception:
        logger.exception("Failed to parse %s (%s)", filename, code_name)
        return {}

    transformer = _DeclarationsTransformer(
        str(filename.resolve()),
        parsed,
        line_number_offset=line_offset,
    )
    transformer.transform(parsed)
    return transformer.declarations


@dataclass
class PlcSymbolMetadata:
    context: FullLoadContext
    name: str
    type: str


@dataclass
class Dependency:
    name: str
    vendor: str
    version: str
    vendor_short: str


_dependency_store = None


@dataclass
class DependencyStoreLibrary:
    name: str
    versioned: bool
    path: str
    project: str

    def get_latest_version_path(self, root: pathlib.Path) -> pathlib.Path:
        """
        Get the latest version project filename.

        Returns
        -------
        pathlib.Path
        """
        def get_version(path):
            try:
                version = path.name.lstrip('v').replace('-', '.')
                version = tuple(distutils.version.LooseVersion(version).version)
                if isinstance(version[0], int):
                    return version
            except Exception:
                ...

        project_root = root / self.path

        paths = {
            (get_version(path), path) for path in project_root.iterdir()
            if get_version(path) is not None
        }

        for version, path in reversed(sorted(paths)):
            project_fn = path / self.project
            if project_fn.exists():
                logger.debug(
                    'Found latest %s (%s) in %s',
                    self.name, version, project_fn
                )
                return project_fn

        raise FileNotFoundError(
            f'No valid versions of {self.name} found in {project_root}'
        )

    def get_project_filename(self, root: pathlib.Path, version: str) -> pathlib.Path:
        """Get the full project filename, given the root path and version."""
        if not self.versioned:
            return root / self.path / self.project
        if version == "*":
            return self.get_latest_version_path(root) / self.project

        return root / self.path / version / self.project


@dataclass
class DependencyStoreConfig:
    libraries: Dict[str, DependencyStoreLibrary]


class DependencyStore:
    """
    A storage container for dependency configuration and loading.

    Environment variable: ``WHATRECORD_TWINCAT_ROOT`` is required to be set for
    this to be functional, along with a "config.json" in that directory.  This
    should contain information as to the supported library dependencies and
    where to find them.

    .. code::

        {
            "libraries": {
                "LCLS General": {
                    "name": "LCLS General",
                    "versioned": false,
                    "path": "lcls-twincat-general",
                    "project": "LCLSGeneral.sln"
                },
                "lcls-twincat-motion": {
                    "name": "lcls-twincat-motion",
                    "versioned": true,
                    "path": "lcls-twincat-motion",
                    "project": "lcls-twincat-motion.sln"
                }
            }
        }

    The above would indicate that the "LCLS General" library
    (as named in TwinCAT) is available relative to the root directory in
    ``lcls-twincat-general/LCLSGeneral.sln``.
    It would also indicate that the "lcls-twincat-motion" library could
    be found in
    ``lcls-twincat-motion/VERSION/lcls-twincat-motion.sln``
    where VERSION is the project-defined version.
    """
    root: pathlib.Path
    config: DependencyStoreConfig

    def __init__(self, root: pathlib.Path):
        self.root = root
        self.load_config()

    @property
    def config_filename(self):
        """The configuration filename."""
        return (self.root / "config.json").expanduser().resolve()

    def _read_config(self) -> Any:
        with open(self.config_filename) as fp:
            return json.load(fp)

    def load_config(self):
        """Load the dependency store configuration file."""
        try:
            config = self._read_config()
        except FileNotFoundError:
            logger.warning(
                "pytmc dependencies will not be loaded as either "
                "WHATRECORD_TWINCAT_ROOT is unset or invalid.  Expected "
                "file %s to exist",
                self.root / "config.json"
            )
            self.config = DependencyStoreConfig(libraries={})
            return

        self.config = apischema.deserialize(DependencyStoreConfig, config)

    @functools.lru_cache(maxsize=50)
    def get_dependency(self, name: str, version: str) -> List[PlcMetadata]:
        """Get a dependency by name and version number."""
        try:
            info: DependencyStoreLibrary = self.config.libraries[name]
        except KeyError:
            return []

        try:
            filename = info.get_project_filename(self.root, version=version)
        except FileNotFoundError:
            return []

        if not filename.exists():
            return []

        return list(PlcMetadata.from_project_filename(str(filename.resolve())))

    def get_dependencies(
        self, plc: pytmc.parser.Plc,
    ) -> Generator[Tuple[Dependency, PlcMetadata], None, None]:
        """Get dependency projects from a PLC."""
        for resolution in plc.root.find(pytmc.parser.Resolution):
            resolution: pytmc.parser.Resolution
            try:
                info = Dependency(**resolution.resolution)
            except (KeyError, ValueError):
                continue

            for proj in self.get_dependency(info.name, info.version):
                yield info, proj

    @staticmethod
    def get_instance() -> DependencyStore:
        """Get the global DependencyStore instance."""
        return get_dependency_store()


def get_dependency_store() -> DependencyStore:
    """Get the global DependencyStore instance."""
    global _dependency_store

    if _dependency_store is None:
        _dependency_store = DependencyStore(
            root=pathlib.Path(settings.TWINCAT_ROOT)
        )
    return _dependency_store


def _get_records_from_pytmc_symbol(symbol: pytmc.parser.Symbol) -> List[str]:
    """Get record names from a given pytmc symbol."""
    return [
        record.pvname
        for pkg in pytmc.pragmas.record_packages_from_symbol(
            symbol, yield_exceptions=False, allow_no_pragma=False
        )
        for record in pkg.records
    ]


@dataclass
class PlcMetadata:
    name: str
    context: FullLoadContext
    code: Dict[str, PlcCode]
    symbols: Dict[str, PlcSymbolMetadata]
    record_to_symbol: Dict[str, str]
    dependencies: Dict[str, Dependency]

    def find_declaration_from_symbol(self, name: str) -> Optional[Declaration]:
        """Given a symbol name, find its Declaration."""
        parts = collections.deque(name.split("."))
        if len(parts) <= 1:
            return

        variable_name = parts.pop()
        parent = None
        path = []
        while parts:
            part = parts.popleft()
            if "[" in part:  # ]
                part = part.split("[")[0]  # ]

            try:
                if parent is None:
                    parent: PlcCode = self.code[part]
                else:
                    part_type = parent.declarations[part].type
                    parent: PlcCode = self.code[part_type]
            except KeyError:
                return

            path.append(parent)

        try:
            return parent.declarations[variable_name]
        except KeyError:
            # Likely ``EXTENDS``, which is not yet supported
            ...

    def get_symbol_context(
        self,
        symbol: pytmc.parser.Symbol,
    ) -> FullLoadContext:
        """Get context information for a given pytmc Symbol."""
        context = []
        try:
            symbol_context = self.code[symbol.data_type.name].context
        except KeyError:
            ...
        else:
            context.extend(symbol_context)

        decl = self.find_declaration_from_symbol(symbol.name)
        if decl is not None:
            context.extend(decl.context)
        return tuple(context)

    def get_symbol_metadata(
        self,
        symbol: pytmc.parser.Symbol,
        require_records: bool = True
    ) -> Optional[PlcSymbolMetadata]:
        """Get symbol metadata given a pytmc Symbol."""
        context = self.get_symbol_context(symbol)
        if not context:
            # If the declaration had no context somehow, then this isn't a
            # useful entry
            return

        records = _get_records_from_pytmc_symbol(symbol)

        if records or not require_records:
            annotated_name = f"{self.name}:{symbol.name}"
            for record in records:
                self.record_to_symbol[record] = annotated_name

            return PlcSymbolMetadata(
                context=tuple(context),
                name=symbol.name,
                type=symbol.data_type.name,
            )

    @classmethod
    def from_pytmc(
        cls,
        plc: pytmc.parser.Plc,
        include_dependencies: bool = True,
        include_symbols: bool = True,
    ) -> PlcMetadata:
        """Create a PlcMetadata instance from a pytmc-parsed one."""
        tmc = plc.tmc
        if tmc is None and include_symbols:
            logger.debug("%s: No TMC file for symbols; skipping...", plc.name)
            return

        code = {}
        deps = {}
        symbols = {}

        if include_dependencies:
            store = get_dependency_store()
            for resolution, proj in store.get_dependencies(plc):
                code.update(proj.code)
                deps.update(proj.dependencies)
                deps[resolution.name] = resolution

        for code_obj in PlcCode.from_pytmc_plc(plc):
            code[code_obj.name] = code_obj

        md = cls(
            name=plc.name,
            context=(LoadContext(str(plc.filename.resolve()), 0), ),
            code=code,
            symbols=symbols,
            record_to_symbol={},
            dependencies=deps,
        )

        if not include_symbols:
            return md

        all_symbols = [symbol for symbol in tmc.find(pytmc.parser.Symbol)]

        def by_name(symbol):
            return symbol.name

        for symbol in sorted(all_symbols, key=by_name):
            symbol_md = md.get_symbol_metadata(symbol)
            if symbol_md is not None:
                symbols[symbol.name] = symbol_md

        logger.debug(
            "%s: Found %d symbols (%d generated metadata)",
            plc.name, len(all_symbols), len(symbols)
        )
        return md

    @classmethod
    def from_project_filename(
        cls,
        project: str,
        include_dependencies: bool = True,
        include_symbols: bool = True
    ) -> Generator[PlcMetadata, None, None]:
        solution_path, projects = get_tsprojects_from_filename(project)
        logger.debug("Solution path %s projects %s", solution_path, projects)
        for tsproj_project in projects:
            logger.debug("Found tsproj %s", tsproj_project.name)
            parsed_tsproj = pytmc.parser.parse(tsproj_project)
            for plc_name, plc in parsed_tsproj.plcs_by_name.items():
                logger.debug("Found plc project %s", plc_name)
                plc_md = cls.from_pytmc(
                    plc, include_dependencies=include_dependencies,
                    include_symbols=include_symbols
                )
                if plc_md is not None:
                    yield plc_md


# @suppress_output_decorator
def main(project: str, pretty: bool = False, verbose: bool = False):
    if verbose:
        logging.basicConfig(level="DEBUG")
        logging.getLogger("parso").setLevel("WARNING")
    return list(PlcMetadata.from_project_filename(project))


def _cli_main():
    parser = _get_argparser()
    args = parser.parse_args()
    results = main(**vars(args))

    whatrecord_results = PytmcPluginResults.from_metadata_items(results)
    json_results = apischema.serialize(whatrecord_results)
    if False:
        dump_args = {"indent": 4} if args.pretty else {}
        print(json.dumps(json_results, sort_keys=True, **dump_args))
    return results


def _get_argparser(parser: typing.Optional[argparse.ArgumentParser] = None):
    if parser is None:
        parser = argparse.ArgumentParser(description=DESCRIPTION)

    parser.add_argument(
        "project", help="TwinCAT Project to parse"
    )
    # parser.add_argument(
    #     "--server", help="WhatRecord API server URL"
    # )
    parser.add_argument(
        "-p", "--pretty", action="store_true", help="Pretty JSON output"
    )
    parser.add_argument(
        "-v", "--verbose", action="store_true", help="Verbose logging"
    )
    return parser


if __name__ == "__main__":
    results = _cli_main()
