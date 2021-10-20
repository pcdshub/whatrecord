"""
LCLS-specific epicsArch.txt plugin.
"""

from __future__ import annotations

import argparse
import json
import logging
import pathlib
import typing
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Type

import apischema
import lark

from .. import transformer
from ..common import AnyPath, FullLoadContext, StringWithContext
from ..db import split_record_and_field
from ..server.common import PluginResults
from ..util import get_bytes_sha256

logger = logging.getLogger(__name__)

# Stash the description for later usage by the CLI interface.
DESCRIPTION = __doc__.strip()


@dataclass
class LclsEpicsArchPluginResults(PluginResults):
    # Could potentially further specify metadata_by_key or metadata
    ...


@dataclass
class Comment:
    context: FullLoadContext
    text: str


@dataclass
class Warning:
    context: FullLoadContext
    type_: str
    text: str


@dataclass
class DaqPV:
    context: FullLoadContext
    name: str
    alias: str = ""
    provider: str = "ca"
    comments: List[Comment] = field(default_factory=list)


@dataclass
class LclsEpicsArchFile:
    """Representation of an LCLS-specific DAQ recording epicsArch.txt file."""
    pvs: Dict[str, DaqPV]
    aliases: Dict[str, str]
    warnings: List[Warning]
    filename: Optional[pathlib.Path] = None
    loaded_files: Dict[str, str] = field(default_factory=dict)

    @classmethod
    def from_string(
        cls,
        contents: str,
        filename: Optional[AnyPath] = None,
        debug: bool = False,
        context: Optional[FullLoadContext] = None,
    ) -> LclsEpicsArchFile:
        """Load an epicsArch.txt file given its string contents."""
        if filename:
            filename = pathlib.Path(filename).resolve()

        grammar = lark.Lark.open_from_package(
            "whatrecord",
            "lcls_epicsarch.lark",
            search_paths=("grammar",),
            parser="earley",
            propagate_positions=True,
            debug=debug,
        )

        transformer_ = _EpicsArchTransformer(
            cls, filename, contents, grammar, context=context
        )
        return transformer_.transform(grammar.parse(contents + "\n"))

    @classmethod
    def from_file_obj(
        cls, fp, filename: Optional[AnyPath] = None,
        context: Optional[FullLoadContext] = None,
    ) -> LclsEpicsArchFile:
        """Load an epicsArch.txt file from a file object."""
        return cls.from_string(
            fp.read(),
            filename=getattr(fp, "name", filename),
            context=context,
        )

    @classmethod
    def from_file(
        cls, fn: AnyPath,
        context: Optional[FullLoadContext] = None,
    ) -> LclsEpicsArchFile:
        """
        Load an epicsArch.txt file.

        Parameters
        ----------
        filename : pathlib.Path or str
            The filename.

        Returns
        -------
        file : LclsEpicsArchFile
            The parsed file.
        """
        with open(fn, "rt") as fp:
            return cls.from_string(fp.read(), filename=fn, context=context)


@lark.visitors.v_args(inline=True)
class _EpicsArchTransformer(lark.visitors.Transformer):
    cls: Type[LclsEpicsArchFile]
    fn: str
    _load_context: FullLoadContext
    _loaded_files: Dict[str, str]
    _path: pathlib.Path
    _pvs: Dict[str, DaqPV]
    _aliases: Dict[str, DaqPV]
    _comments: List[Comment]
    _warnings: List[Warning]
    _grammar: lark.Grammar

    def __init__(
        self,
        cls,
        fn: Optional[pathlib.Path],
        raw_contents: str,
        grammar: lark.Grammar,
        context: Optional[FullLoadContext] = None,
        visit_tokens=False,
    ):
        super().__init__(visit_tokens=visit_tokens)
        self.fn = str(fn)
        self.cls = cls
        self._loaded_files = {}
        self._load_context = context or ()
        self._aliases = {}
        self._comments = []
        self._grammar = grammar
        self._path = fn.resolve() if fn else pathlib.Path(".")
        self._pvs = {}
        self._warnings = []

        if not fn:
            return

        self._loaded_files[str(fn)] = get_bytes_sha256(
            raw_contents.encode("utf-8")
        )

    def archfile(self, *entries):
        return self.cls(
            pvs=self._pvs,
            filename=pathlib.Path(self.fn).resolve(),
            warnings=self._warnings,
            aliases=self._aliases,
            loaded_files=self._loaded_files,
        )

    pvname = transformer.pass_through
    comment_text = transformer.pass_through

    def comment(self, comment_token, comment=None, *_):
        self._comments.append(
            Comment(
                context=transformer.context_from_token(self.fn, comment_token),
                text=str(comment).strip().lstrip("# \t"),
            )
        )

    def pv(self, pvname, *extra):
        """pvname (_WS+ provider)? EOL"""
        if len(extra) > 1:
            provider, *_ = extra
        else:
            provider = "ca"

        pv = DaqPV(
            context=transformer.context_from_token(self.fn, pvname),
            name=str(pvname),
            provider=str(provider),
        )

        self._add_pv(pv, updating=False)
        return pv

    def description(self, desc_prefix, desc_text, _):
        """DESC_PREFIX _WS* DESC_TEXT EOL"""
        return StringWithContext(
            desc_text,
            context=transformer.context_from_token(self.fn, desc_prefix)
        )

    pvs = transformer.tuple_args

    def _add_pv(self, pv: DaqPV, updating: bool = False):
        if pv.name in self._pvs and not updating:
            old_pv = self._pvs[pv.name]
            self._warnings.append(
                Warning(
                    context=pv.context,
                    type_="duplicate_pv",
                    text=f"Duplicate pvname: {pv.name} {old_pv.context}"
                )
            )

        if pv.alias in self._aliases:
            old_pv = self._pvs[self._aliases[pv.alias]]
            self._warnings.append(
                Warning(
                    context=pv.context,
                    type_="duplicate_alias",
                    text=f"Duplicate alias: {pv.alias} {old_pv.context}",
                )
            )

        if pv.alias in self._pvs:
            old_pv = self._pvs[pv.alias]
            self._warnings.append(
                Warning(
                    context=pv.context,
                    type_="alias_is_pv",
                    text=f"Alias name is a PV: {pv.alias} {old_pv.context}",
                )
            )

        if pv.name in self._aliases:
            old_pv = self._pvs[self._aliases[pv.name]]
            self._warnings.append(
                Warning(
                    context=pv.context,
                    type_="pv_is_alias",
                    text=f"PV name matches alias: {pv.name} {old_pv.context}",
                )
            )

        if pv.name not in self._pvs:
            self._pvs[pv.name] = pv
            # Tack on our load context
            pv.context = self._load_context[-1:] + pv.context

        if pv.alias:
            self._aliases[pv.alias] = pv.name

    def description_group(self, description, *items):
        if not items:
            return

        pvs = [item for item in items if isinstance(item, DaqPV)]
        # TODO
        # comments = [item for item in items if isinstance(item, Comment)]
        for idx, pv in enumerate(pvs, 1):
            if idx > 1:
                # NOTE: the old daq docs indicate it appended "-{pv}" on the
                # description... but the new source does this:
                pv.alias = f"{description}_{idx}"
            else:
                pv.alias = description

            pv.comments = list(self._comments)
            self._add_pv(pv, updating=True)

        self._comments = []

    def filenames(self, *filenames):
        return filenames

    def include(self, include_token, filenames, _):
        include_ctx = transformer.context_from_token(self.fn, include_token)
        for filename in filenames:
            filename = (self._path.parent / filename).resolve()
            if (
                any(ctx.name == str(filename) for ctx in self._load_context)
                or filename == self._path
            ):
                self._warnings.append(
                    Warning(
                        context=include_ctx,
                        type_="recursive_include",
                        text=(
                            f"Recursively included {filename} at "
                            f"{include_ctx[0]} {self._load_context}"
                        ),
                    )
                )
                continue

            try:
                included = self.cls.from_file(
                    filename,
                    context=self._load_context + include_ctx,
                )
            except lark.exceptions.LarkError as ex:
                self._warnings.append(
                    Warning(
                        context=include_ctx,
                        type_="bad_file",
                        text=(
                            f"Failed to parse {filename}: {ex.__class__.__name__} {ex}"
                        )
                    )
                )
            except FileNotFoundError:
                self._warnings.append(
                    Warning(
                        context=include_ctx,
                        type_="missing_file",
                        text=f"Included {filename} missing"
                    )
                )
            else:
                self._warnings.extend(included.warnings)
                for pv in included.pvs.values():
                    self._add_pv(pv, updating=False)
                self._loaded_files.update(included.loaded_files)

        def blank_line(self, *_):
            ...


def main(
    filenames: List[str],
    pretty: bool = False,
):
    by_filename = {}
    record_to_file = {}
    execution_info = {}
    files_to_monitor = {}
    for filename in sorted(filenames):
        try:
            archfile = LclsEpicsArchFile.from_file(filename)
        except Exception as ex:
            execution_info[str(filename)] = (
                f"Failed to load: {ex.__class__.__name__} {ex}"
            )
            continue

        files_to_monitor.update(archfile.loaded_files)
        filename = str(filename)
        by_filename[filename] = archfile
        for pv in sorted(archfile.pvs):
            record, _ = split_record_and_field(pv)
            record_to_file.setdefault(record, []).append(filename)

    return LclsEpicsArchPluginResults(
        files_to_monitor=files_to_monitor,
        record_to_metadata_keys=record_to_file,
        metadata={},
        metadata_by_key=by_filename,
        execution_info=execution_info,
    )


def _get_argparser(
    parser: typing.Optional[argparse.ArgumentParser] = None,
) -> argparse.ArgumentParser:
    if parser is None:
        parser = argparse.ArgumentParser(description=DESCRIPTION)

    pds_root = pathlib.Path("/cds/group/pcds/dist/pds")
    if pds_root.exists():
        default_files = (
            tuple(pds_root.glob("*/misc/epicsArch.txt")) +
            tuple(pds_root.glob("*/misc/logbook.txt"))
        )
    else:
        default_files = ()

    parser.add_argument(
        "-f", "--filename",
        dest="filenames",
        type=str,
        nargs="+",
        required=False,
        help="Filenames",
        default=default_files,
    )

    parser.add_argument(
        "-p", "--pretty", action="store_true", help="Pretty JSON output"
    )
    return parser


def _cli_main():
    parser = _get_argparser()
    kwargs = vars(parser.parse_args())
    results = main(**kwargs)
    json_results = apischema.serialize(results)
    dump_args = {"indent": 4} if kwargs["pretty"] else {}
    print(json.dumps(json_results, sort_keys=True, **dump_args))


if __name__ == "__main__":
    _cli_main()
