"""
TwinCAT / pytmc whatrecord plugin

Match your TwinCAT project symbols to EPICS records.

Set ``project`` to generate metadata for one particular PLC project.

Alternatively, the plugin will query WHATRECORD_SERVER for all IOCs and attempt
to find ads-ioc-based IOCs with associated TwinCAT projects.
"""
from __future__ import annotations

import argparse
import asyncio
import collections
import distutils.version
import functools
import json
import logging
import pathlib
import re
import typing
from dataclasses import dataclass
from typing import Any, Dict, Generator, Iterable, List, Optional, Tuple

import apischema
import blark
import blark.parse
import lark
import pytmc
import pytmc.bin.db
import pytmc.code

from .. import cache, client, settings, transformer, util
from ..common import (AnyPath, FullLoadContext, IocMetadata, LoadContext,
                      remove_redundant_context)
from ..server.common import PluginResults
from ..util import get_file_sha256, read_text_file_with_hash

# from .util import suppress_output_decorator

logger = logging.getLogger(__name__)

# Stash the description for later usage by the CLI interface.
DESCRIPTION = __doc__.strip()

BLARK_BUGFIXES = {
    "global": [
        # TODO blark grammar bug in GVLs but not FBs?
        (re.compile(r"FB_Arbiter\(\d+\)"), "FB_Arbiter"),
    ],
}


def get_tsprojects_from_filename(
    filename: AnyPath,
) -> Tuple[pathlib.Path, List[pytmc.parser.TwincatItem]]:
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
    def merge(self, results: PytmcPluginResults) -> None:
        self.files_to_monitor.update(results.files_to_monitor)
        self.record_to_metadata_keys.update(results.record_to_metadata_keys)
        self.metadata_by_key.update(results.metadata_by_key)
        self.execution_info.update(results.execution_info)
        self.nested.update(results.nested)

    @classmethod
    def from_metadata(cls, md: PlcMetadata) -> PytmcPluginResults:
        plc_results = PytmcPluginResults(
            files_to_monitor=md.loaded_files,
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
        return PytmcPluginResults(
            nested={
                md.name: plc_results
            }
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

        if results is not None:
            return results

        return PytmcPluginResults(
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
    name: str
    filename: str
    context: FullLoadContext
    declarations: Dict[str, Declaration]
    hash: str

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
            filename=str(code_obj.filename),
            context=(LoadContext(str(code_obj.filename), 0), ),
            declarations=md_declarations,
            hash=get_file_sha256(code_obj.filename),
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
    filename: str
    hash: str
    axes: List[NCAxis]

    @classmethod
    def from_pytmc(
        cls,
        plc: pytmc.parser.Plc,
    ) -> Optional[NCAxes]:
        """Create an NCAxes instance from a pytmc-parsed Plc."""
        try:
            nc = next(plc.root.find(pytmc.parser.NC))
        except StopIteration:
            return

        filename = str(nc.filename.resolve())

        return cls(
            context=(LoadContext(filename, 0), ),
            filename=filename,
            hash=get_file_sha256(filename),
            axes=[NCAxis.from_pytmc(axis) for axis in nc.axes],
        )


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


def apply_blark_bugfixes(var_section, source):
    """Blark has some work necessary. Patch up common known bugs for now."""
    for bugfix_match, replace_with in BLARK_BUGFIXES.get(var_section, []):
        bugfix_match: re.Pattern
        replace_with: str
        source = bugfix_match.sub(replace_with, source)
    return source


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
        decl_source = apply_blark_bugfixes(var_section, decl_source)
        if var_section == "global":
            # Standalone global section
            source = decl_source
        elif var_section == "type":
            # Standalone struct/type section
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
    include_symbols: bool


@dataclass
class PlcMetadata(cache.InlineCached, PlcMetadataCacheKey):
    """This metadata is keyed on PlcMetadataCacheKey."""
    context: FullLoadContext
    code: Dict[str, PlcCode]
    symbols: Dict[str, PlcSymbolMetadata]
    record_to_symbol: Dict[str, str]
    loaded_files: Dict[str, str]
    dependencies: Dict[str, Dependency]
    nc: Optional[NCAxes] = None

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
        type_name: str,
        symbol_name: str,
    ) -> FullLoadContext:
        """Get context information for a given pytmc Symbol."""
        context = []
        try:
            type_context = self.code[type_name].context
        except KeyError:
            ...
        else:
            context.extend(type_context)

        try:
            code, first_symbol, *_ = symbol_name.split(".")
            first_context = self.code[code].declarations[first_symbol].context
        except Exception:
            ...
        else:
            context.extend(first_context)

        decl = self.find_declaration_from_symbol(symbol_name)
        if decl is not None:
            context.extend(decl.context)

        return tuple(remove_redundant_context(context))

    def get_symbol_metadata(
        self,
        symbol: pytmc.parser.Symbol,
        require_records: bool = True
    ) -> Generator[PlcSymbolMetadata, None, None]:
        """Get symbol metadata given a pytmc Symbol."""
        symbol_type_name = symbol.data_type.qualified_type_name
        for pkg in pytmc.pragmas.record_packages_from_symbol(
            symbol, yield_exceptions=True, allow_no_pragma=False
        ):
            if isinstance(pkg, Exception):
                # Eat these up rather than raising
                continue
            context = self.get_symbol_context(symbol.data_type.name, pkg.tcname)
            if not context:
                # If the declaration had no context somehow, then this isn't a
                # useful entry
                continue

            records = [record.pvname for record in pkg.records]
            if records or not require_records:
                annotated_name = f"{self.name}:{pkg.tcname}"
                for record in records:
                    self.record_to_symbol[record] = annotated_name

                chain_type_name = pkg.chain.data_type.qualified_type_name
                if symbol_type_name == chain_type_name:
                    type_name = symbol_type_name
                else:
                    type_name = f"{chain_type_name} ({symbol_type_name})"

                yield PlcSymbolMetadata(
                    context=tuple(context),
                    name=annotated_name,
                    type=type_name,
                )

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
            str(makefile_path): makefile_hash or get_file_sha256
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
    def from_pytmc(
        cls,
        plc: pytmc.parser.Plc,
        include_dependencies: bool = True,
        include_symbols: bool = True,
        loaded_files: Optional[Dict[str, str]] = None,
        use_cache: bool = True,
    ) -> PlcMetadata:
        """Create a PlcMetadata instance from a pytmc-parsed one."""
        tmc = plc.tmc
        if tmc is None and include_symbols:
            logger.debug("%s: No TMC file for symbols; skipping...", plc.name)
            return

        filename = str(plc.filename.resolve())
        if use_cache:
            key = PlcMetadataCacheKey(
                name=plc.name,
                filename=filename,
                include_dependencies=include_dependencies,
                include_symbols=include_symbols,
            )
            cached = cls.from_cache(key)
            if cached is not None:
                if util.check_files_up_to_date(cached.loaded_files):
                    return cached

        loaded_files = dict(loaded_files or {})
        code = {}
        deps = {}
        symbols = {}

        loaded_files[filename] = util.get_file_sha256(filename)

        if include_dependencies:
            store = get_dependency_store()
            for resolution, proj in store.get_dependencies(plc):
                code.update(proj.code)
                deps.update(proj.dependencies)
                loaded_files.update(proj.loaded_files)
                deps[resolution.name] = resolution

        for code_obj in PlcCode.from_pytmc_plc(plc):
            code[code_obj.name] = code_obj
            loaded_files[code_obj.filename] = code_obj.hash

        nc = NCAxes.from_pytmc(plc)

        if nc is not None:
            loaded_files[nc.filename] = nc.hash
            for axis in nc.axes:
                loaded_files[axis.filename] = axis.hash

        md = cls(
            name=plc.name,
            filename=filename,
            include_dependencies=include_dependencies,
            include_symbols=include_symbols,
            context=(LoadContext(filename, 0), ),
            code=code,
            symbols=symbols,
            record_to_symbol={},
            dependencies=deps,
            loaded_files=loaded_files,
            nc=nc,
        )

        if not include_symbols:
            return md

        all_symbols = list(pytmc.bin.db.find_pytmc_symbols(tmc))

        def by_name(symbol):
            return symbol.name

        for symbol in sorted(all_symbols, key=by_name):
            for symbol_md in md.get_symbol_metadata(symbol):
                symbols[symbol_md.name] = symbol_md

        logger.debug(
            "%s: Found %d symbols (%d generated metadata)",
            plc.name, len(all_symbols), len(symbols)
        )
        if use_cache:
            md.save_to_cache()

        return md

    @classmethod
    def from_project_filename(
        cls,
        project: AnyPath,
        include_dependencies: bool = True,
        include_symbols: bool = True,
        plc_whitelist: Optional[List[str]] = None,
        loaded_files: Optional[Dict[str, str]] = None,
    ) -> Generator[PlcMetadata, None, None]:
        """Given a project/solution filename, get all PlcMetadata."""
        loaded_files = dict(loaded_files or {})
        solution_path, projects = get_tsprojects_from_filename(project)
        logger.debug("Solution path %s projects %s", solution_path, projects)
        for tsproj_project in projects:
            logger.warning("Found tsproj %s", tsproj_project.name)
            try:
                parsed_tsproj = pytmc.parser.parse(tsproj_project)
            except Exception:
                logger.exception("Failed to load project %s", tsproj_project.name)
                continue

            for plc_name, plc in parsed_tsproj.plcs_by_name.items():
                if plc_whitelist and plc_name not in plc_whitelist:
                    continue

                logger.debug("Found plc project %s", plc_name)
                plc_md = cls.from_pytmc(
                    plc,
                    include_dependencies=include_dependencies,
                    include_symbols=include_symbols,
                    loaded_files=loaded_files,
                )
                if plc_md is not None:
                    yield plc_md


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


# @suppress_output_decorator
async def main(
    project: str,
    server: Optional[str] = None,
    pretty: bool = False,
    verbose: bool = False,
    test: bool = False,
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
    whatrecord_results = PytmcPluginResults.from_metadata_items(results)
    json_results = apischema.serialize(whatrecord_results)
    if not args.test:
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
    parser.add_argument(
        "-t", "--test", action="store_true",
        help="Do not output project (for testing)"
    )
    return parser


if __name__ == "__main__":
    results = asyncio.run(_cli_main())
