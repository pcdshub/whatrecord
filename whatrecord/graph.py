import ast
import asyncio
import collections
import copy
import html
import logging
import os
from typing import Dict, List, Optional, Tuple

import graphviz as gv

from .common import (FullLoadContext, LoadContext, PVRelations,
                     ScriptPVRelations, dataclass)
from .db import RecordField, RecordInstance, RecordType

logger = logging.getLogger(__name__)

# TODO: refactor this to not be graphviz-dependent; instead return node/link
# information in terms of dataclasses

# NOTE: the following is borrowed from pygraphviz, reimplemented to allow
# for asyncio compatibility


async def async_render(
    engine, format, filepath, renderer=None, formatter=None, quiet=False
):
    """
    Async Render file with Graphviz ``engine`` into ``format``,  return result
    filename.

    Parameters
    ----------
    engine :
        The layout commmand used for rendering (``'dot'``, ``'neato'``, ...).
    format :
        The output format used for rendering (``'pdf'``, ``'png'``, ...).
    filepath :
        Path to the DOT source file to render.
    renderer :
        The output renderer used for rendering (``'cairo'``, ``'gd'``, ...).
    formatter :
        The output formatter used for rendering (``'cairo'``, ``'gd'``, ...).
    quiet : bool
        Suppress ``stderr`` output from the layout subprocess.

    Returns
    -------
    The (possibly relative) path of the rendered file.

    Raises
    ------
    ValueError: If ``engine``, ``format``, ``renderer``, or ``formatter`` are not known.
    graphviz.RequiredArgumentError: If ``formatter`` is given but ``renderer`` is None.
    graphviz.ExecutableNotFound: If the Graphviz executable is not found.
    subprocess.CalledProcessError: If the exit status is non-zero.

    Notes
    -----
    The layout command is started from the directory of ``filepath``, so that
    references to external files (e.g. ``[image=...]``) can be given as paths
    relative to the DOT source file.
    """
    # Adapted from graphviz under the MIT License (MIT) Copyright (c) 2013-2020
    # Sebastian Bank
    dirname, filename = os.path.split(filepath)

    cmd, rendered = gv.backend.command(engine, format, filename, renderer, formatter)
    if dirname:
        cwd = dirname
        rendered = os.path.join(dirname, rendered)
    else:
        cwd = None

    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        cwd=cwd,
    )

    (stdout, stderr) = await proc.communicate()
    if proc.returncode:
        raise gv.backend.CalledProcessError(
            proc.returncode, cmd, output=stdout, stderr=stderr
        )
    return rendered


class AsyncDigraph(gv.Digraph):
    async def async_render(
        self,
        filename=None,
        directory=None,
        view=False,
        cleanup=False,
        format=None,
        renderer=None,
        formatter=None,
        quiet=False,
        quiet_view=False,
    ):
        """
        Save the source to file and render with the Graphviz engine.

        Parameters
        ----------
        filename :
            Filename for saving the source (defaults to ``name`` + ``'.gv'``)
        directory :
            (Sub)directory for source saving and rendering.
        view (bool) :
            Open the rendered result with the default application.
        cleanup (bool) :
            Delete the source file after rendering.
        format :
            The output format used for rendering (``'pdf'``, ``'png'``, etc.).
        renderer :
            The output renderer used for rendering (``'cairo'``, ``'gd'``, ...).
        formatter :
            The output formatter used for rendering (``'cairo'``, ``'gd'``, ...).
        quiet (bool) :
            Suppress ``stderr`` output from the layout subprocess.
        quiet_view (bool) :
            Suppress ``stderr`` output from the viewer process;
           implies ``view=True``, ineffective on Windows.
        Returns:
            The (possibly relative) path of the rendered file.

        Raises
        ------
        ValueError: If ``format``, ``renderer``, or ``formatter`` are not known.
        graphviz.RequiredArgumentError: If ``formatter`` is given but ``renderer`` is None.
        graphviz.ExecutableNotFound: If the Graphviz executable is not found.
        subprocess.CalledProcessError: If the exit status is non-zero.
        RuntimeError: If viewer opening is requested but not supported.

        Notes
        -----
        The layout command is started from the directory of ``filepath``, so that
        references to external files (e.g. ``[image=...]``) can be given as paths
        relative to the DOT source file.
        """
        # Adapted from graphviz under the MIT License (MIT) Copyright (c) 2013-2020
        # Sebastian Bank
        filepath = self.save(filename, directory)

        if format is None:
            format = self._format

        rendered = await async_render(
            self._engine,
            format,
            filepath,
            renderer=renderer,
            formatter=formatter,
            quiet=quiet,
        )

        if cleanup:
            logger.debug("delete %r", filepath)
            os.remove(filepath)

        if quiet_view or view:
            self._view(rendered, self._format, quiet_view)

        return rendered


@dataclass
class LinkInfo:
    record1: RecordInstance
    field1: RecordField
    record2: RecordInstance
    field2: RecordField
    # info: Tuple[str, ...]
    info: List[str]


def is_supported_link(link: str) -> bool:
    if link.startswith("#") or link.startswith("0x") or link.startswith("@"):
        return False
    try:
        ast.literal_eval(link)
    except Exception:
        # Should not be an integer literal
        return True

    return False


def build_database_relations(
    database: Dict[str, RecordInstance],
    record_types: Optional[Dict[str, RecordType]] = None,
    aliases: Optional[Dict[str, str]] = None
) -> PVRelations:
    """
    Build a dictionary of PV relationships.

    This should not be called often for large databases, as it makes no attempt
    to be computationally efficient.  For repeated usage, cache the result
    of this function and reuse it in future calls to ``graph_links`` and such.

    Parameters
    ----------
    database : dict
        Dictionary of record name to record instance.

    record_types : dict, optional
        The database definitions to use for fields that are not defined in the
        database file.  Dictionary of record type name to RecordType.

    Returns
    -------
    info : dict
        Such that: ``info[pv1][pv2] = (field1, field2, info)``
        And in reverse: ``info[pv2][pv1] = (field2, field1, info)``
    """
    aliases = aliases or {}
    warned = set()
    unset_ctx: FullLoadContext = (LoadContext("unknown", 0), )
    by_record = collections.defaultdict(lambda: collections.defaultdict(list))

    # TODO: alias handling?
    for rec1 in database.values():
        for field1, link, info in rec1.get_links():
            # TODO: copied without thinking about implications
            # due to the removal of st.cmd context as an attempt to reduce
            field1 = copy.deepcopy(field1)
            # field1.context = rec1.context[:1] + field1.context

            if "." in link:
                link, field2 = link.split(".")
            elif field1.name == "FLNK":
                field2 = "PROC"
            else:
                field2 = "VAL"

            rec2 = database.get(aliases.get(link, link), None)
            if rec2 is None:
                # TODO: switch to debug; this will be expensive later
                if not is_supported_link(link):
                    continue

                if link not in warned:
                    warned.add(link)
                    logger.debug(
                        "Linked record from %s.%s not in database: %s",
                        rec1.name, field1.name, link
                    )

                field2 = RecordField(
                    dtype="unknown",
                    name=field2,
                    value="(unknown-record)",
                    context=unset_ctx,
                )
                rec2_name = link
            elif field2 in rec2.fields:
                rec2_name = rec2.name
                # TODO: copied without thinking about implications
                field2 = copy.deepcopy(rec2.fields[field2])
                # field2.context = rec2.context[:1] + field2.context
            elif record_types:
                rec2_name = rec2.name
                dbd_record_type = record_types.get(rec2.record_type, None)
                if dbd_record_type is None:
                    field2 = RecordField(
                        dtype="invalid",
                        name=field2,
                        value="(invalid-record-type)",
                        context=unset_ctx,
                    )
                elif field2 not in dbd_record_type.fields:
                    field2 = RecordField(
                        dtype="invalid",
                        name=field2,
                        value="(invalid-field)",
                        context=unset_ctx,
                    )
                else:
                    dbd_record_field = dbd_record_type.fields[field2]
                    field2 = RecordField(
                        dtype=dbd_record_field.type,
                        name=field2,
                        value="",
                        context=dbd_record_field.context,
                    )
            else:
                rec2_name = rec2.name
                field2 = RecordField(
                    dtype="unknown",
                    name=field2,
                    value="",  # unset or invalid, can't tell yet
                    context=unset_ctx,
                )

            by_record[rec1.name][rec2_name].append((field1, field2, info))
            by_record[rec2_name][rec1.name].append((field2, field1, info))

    return dict(
        (key, dict(inner_dict))
        for key, inner_dict in by_record.items()
    )


def combine_relations(
    dest_relations: PVRelations,
    dest_db: Dict[str, RecordInstance],
    source_relations: PVRelations,
    source_db: Dict[str, RecordInstance],
    record_types: Optional[Dict[str, RecordType]] = None,
    aliases: Optional[Dict[str, str]] = None,
):
    """Combine multiple script relations into one."""
    aliases = aliases or {}

    def get_relation_by_field() -> Tuple[
        str, str, Dict[Tuple[str, str], Tuple[str, str, List[str]]]
    ]:
        for rec1_name, rec2_names in source_relations.items():
            dest_rec1_dict = dest_relations.setdefault(rec1_name, {})
            for rec2_name in rec2_names:
                dest_rec2 = dest_rec1_dict.setdefault(rec2_name, [])
                relation_by_field = {
                    (field1.name, field2.name): (field1, field2, link)
                    for field1, field2, link in dest_rec2
                }
                yield rec1_name, rec2_name, relation_by_field

    # Part 1:
    # Rebuild with new aliases, if available
    # Either set of relations could have referred to aliased names, actual
    # names, or even *both*.

    def alias_to_actual(d):
        # This is kinda expensive, imperfect, and confusing; consider reworking
        for alias_from, alias_to in aliases.items():
            # A -> B
            inner_dict = d.pop(alias_from, None)
            if not inner_dict:
                continue

            # Fix up B <- A first, since it's symmetric
            for inner_name, inner_items in inner_dict.items():
                # d[inner_name][alias_to] += d[inner_name][alias_from]
                d[inner_name].setdefault(alias_to, []).extend(
                    d[inner_name].pop(alias_from)
                )

            if alias_to not in d:
                d[alias_to] = inner_dict
            else:
                # The actual record name is already in the relation dict
                for inner_name, inner_items in inner_dict.items():
                    # d[alias_to][inner_name] += inner_items
                    d[alias_to].setdefault(inner_name, []).extend(inner_items)

    alias_to_actual(dest_relations)
    alias_to_actual(source_relations)

    # Part 1:
    # Merge in new or updated relations from the second set
    for rec1_name, rec2_name, relation_by_field in get_relation_by_field():
        for field1, field2, link in source_relations[rec1_name][rec2_name]:
            key = (field1.name, field2.name)
            existing_link = relation_by_field.get(key, None)
            if not existing_link:
                relation_by_field[key] = (field1, field2, link)
            else:
                existing_field1, existing_field2, _ = existing_link
                existing_field1.update_unknowns(field1)
                existing_field2.update_unknowns(field2)

        dest_relations[rec1_name][rec2_name] = list(relation_by_field.values())

    def get_record(name) -> RecordInstance:
        """Get record from either database."""
        name = aliases.get(name, name)
        try:
            return dest_db.get(name, None) or source_db[name]
        except KeyError:
            raise

    def get_field_info(record, field):
        """Get record definition if available."""
        if field in record.fields:
            return record.fields[field]
        if record_types:
            field_def = record_types[field]
            return RecordField(
                dtype=field_def.type,
                name=field,
                value="",
                context=field_def.context,
            )

        raise KeyError("Field not in database or database definition")

    # Part 2:
    # Update any existing relations in the destination relations with
    # information from the source database
    for rec1_name, rec1 in source_db.items():
        if rec1_name in dest_relations:
            for rec2_name, rec2_items in dest_relations[rec1_name].items():
                # We know rec1 is in the source database, but we don't know
                # where rec2 might be, so use `get_record`.
                try:
                    rec2 = get_record(rec2_name)
                except KeyError:
                    # It's not in this IOC...
                    continue

                def get_items_to_update():
                    for field1, field2, _ in rec2_items:
                        yield (rec1, field1)
                        yield (rec2, field2)
                    for field1, field2, _ in dest_relations[rec2_name][rec1_name]:
                        yield (rec2, field1)
                        yield (rec1, field2)

                for rec, field in get_items_to_update():
                    try:
                        field_info = get_field_info(rec, field.name)
                    except KeyError:
                        logger.debug("Missing field? %s.%s", rec.name, field.name)
                    else:
                        field.update_unknowns(field_info)


def find_record_links(database, starting_records, check_all=True, relations=None):
    """
    Get all related record links from a set of starting records.

    All starting records will be included, along with any other records that
    are linked to from there.

    Parameters
    ----------
    database : dict
        Dictionary of record name to record instance.

    starting_records : list of str
        Record names

    relations : dict, optional
        Pre-built PV relationship dictionary.  Generated from database
        if not provided.

    Yields
    -------
    link_info : LinkInfo
        Link info
    """
    checked = []

    if relations is None:
        relations = build_database_relations(database)

    records_to_check = list(starting_records)

    while records_to_check:
        rec1 = database.get(records_to_check.pop(), None)
        if rec1 is None:
            continue

        checked.append(rec1.name)
        logger.debug("--- record %s ---", rec1.name)

        for rec2_name, fields in relations.get(rec1.name, {}).items():
            if rec2_name in checked:
                continue

            rec2 = database.get(rec2_name, None)
            if rec2 is None:
                continue

            for field1, field2, info in fields:
                if rec2_name not in checked and rec2_name not in records_to_check:
                    records_to_check.append(rec2_name)

                li = LinkInfo(
                    record1=rec1,
                    field1=field1,
                    record2=rec2,
                    field2=field2,
                    info=info,
                )

                logger.debug("Link %s", li)
                yield li


def graph_links(
    database,
    starting_records,
    graph=None,
    engine="dot",
    header_format='record({rtype}, "{name}")',
    field_format='{field:>4s}: "{value}"',
    sort_fields=True,
    text_format=None,
    show_empty=False,
    font_name="Courier",
    relations=None,
):
    """
    Create a graphviz digraph of record links.

    All starting records will be included, along with any other records that
    are linked to from there - if available in the database.

    Parameters
    ----------
    database : dict
        Dictionary of record name to record instance.
    starting_records : list of str
        Record names
    graph : graphviz.Graph, optional
        Graph instance to use. New one created if not specified.
    engine : str, optional
        Graphviz engine (dot, fdp, etc)
    field_format : str, optional
        Format string for fields (keys: field, value, attr)
    sort_fields : bool, optional
        Sort list of fields
    text_format : str, optional
        Text format for full node (keys: header, field_lines)
    show_empty : bool, optional
        Show empty fields
    font_name : str, optional
        Font name to use for all nodes and edges
    relations : dict, optional
        Pre-built PV relationship dictionary.  Generated from database
        if not provided.

    Returns
    -------
    nodes: dict
    edges: dict
    graph : AsyncDigraph
    """
    node_id = 0
    edges = []
    nodes = {}
    existing_edges = set()

    if graph is None:
        graph = AsyncDigraph(format="pdf")

    if font_name is not None:
        graph.attr("graph", dict(fontname=font_name))
        graph.attr("node", dict(fontname=font_name))
        graph.attr("edge", dict(fontname=font_name))

    if engine is not None:
        graph.engine = engine

    newline = '<br align="left"/>'
    if text_format is None:
        text_format = f"""<b>{{header}}</b>{newline}{newline}{{field_lines}}"""

    # graph.attr("node", {"shape": "record"})

    def new_node(rec, field=""):
        nonlocal node_id
        node_id += 1
        nodes[rec.name] = dict(id=str(node_id), text=[], record=rec)
        # graph.node(nodes[rec.name], label=field)
        logger.debug("Created node %s (field: %r)", rec.name, field)

    # TODO: create node and color when not in database?

    for li in find_record_links(database, starting_records, relations=relations):
        for (rec, field) in ((li.record1, li.field1), (li.record2, li.field2)):
            if rec.name not in nodes:
                new_node(rec, field)

        src, dest = nodes[li.record1.name], nodes[li.record2.name]

        for field, text in [(li.field1, src["text"]), (li.field2, dest["text"])]:
            if field.value or show_empty:
                text_line = field_format.format(field=field.name, value=field.value)
                if text_line not in text:
                    text.append(text_line)

        if li.field1.dtype == "DBF_INLINK":
            src, dest = dest, src
            li.field1, li.field2 = li.field2, li.field1

        logger.debug("New edge %s -> %s", src, dest)

        edge_kw = {}
        if any(item in li.info for item in {"PP", "CPP", "CP"}):
            edge_kw["style"] = ""
        else:
            edge_kw["style"] = "dashed"

        if any(item in li.info for item in {"MS", "MSS", "MSI"}):
            edge_kw["color"] = "red"

        src_id, dest_id = src["id"], dest["id"]
        if (src_id, dest_id) not in existing_edges:
            edge_kw["xlabel"] = f"{li.field1.name}/{li.field2.name}"
            if li.info:
                edge_kw["xlabel"] += f"\n{' '.join(li.info)}"
            edges.append((src_id, dest_id, edge_kw))
            existing_edges.add((src_id, dest_id))

    if not nodes:
        # No relationship found; at least show the records
        for rec_name in starting_records:
            try:
                new_node(database[rec_name])
            except KeyError:
                ...

    for _, node in sorted(nodes.items()):
        field_lines = node["text"]
        if sort_fields:
            field_lines.sort()

        if field_lines:
            field_lines.append("")

        rec = node["record"]
        header = header_format.format(rtype=rec.record_type, name=rec.name)
        if rec.aliases:
            header += f"\nAlias: {', '.join(rec.aliases)}"

        text = text_format.format(
            header=html.escape(header, quote=False).replace("\n", newline),
            field_lines=newline.join(
                html.escape(line, quote=False) for line in field_lines
            ),
        )
        graph.node(
            node["id"],
            label="< {} >".format(text),
            shape="box3d" if rec.name in starting_records else "rectangle",
            fillcolor="bisque" if rec.name in starting_records else "white",
            style="filled",
        )

    # add all of the edges between graphs
    for src, dest, options in edges:
        graph.edge(src, dest, **options)

    return nodes, edges, graph


def build_script_relations(
    database: Dict[str, RecordInstance],
    by_record: Dict[str, RecordInstance],
    limit_to_records: Optional[List[str]] = None
) -> ScriptPVRelations:
    if limit_to_records is None:
        record_items = by_record.items()
    else:
        record_items = [
            (name, database[name]) for name in limit_to_records
            if name in database
        ]

    def get_owner(rec):
        if not rec:
            return "unknown"

        if rec.owner and rec.owner != "unknown":
            return rec.owner

        if rec.context:
            return rec.context[0].name

        return "unknown"

    by_script = collections.defaultdict(lambda: collections.defaultdict(set))
    for rec1_name, list_of_rec2s in record_items:
        rec1 = database.get(rec1_name, None)
        for rec2_name in list_of_rec2s:
            rec2 = database.get(rec2_name, None)

            owner1 = get_owner(rec1)
            owner2 = get_owner(rec2)
            # print(rec1_name, owner1, "|", rec2_name, owner2)

            if owner1 != owner2:
                by_script[owner2][owner1].add(rec2_name)
                by_script[owner1][owner2].add(rec1_name)

    return by_script


def graph_script_relations(
    database,
    limit_to_records=None,
    graph=None,
    engine="dot",
    header_format='record({rtype}, "{name}")',
    field_format='{field:>4s}: "{value}"',
    text_format=None,
    font_name="Courier",
    relations=None,
    script_relations=None,
):
    """
    Create a graphviz digraph of script links (i.e., inter-IOC record links).

    Parameters
    ----------
    database : dict
        Dictionary of record name to record instance.
    starting_records : list of str
        Record names
    graph : graphviz.Graph, optional
        Graph instance to use. New one created if not specified.
    engine : str, optional
        Graphviz engine (dot, fdp, etc)
    sort_fields : bool, optional
        Sort list of fields
    show_empty : bool, optional
        Show empty fields
    font_name : str, optional
        Font name to use for all nodes and edges
    relations : dict, optional
        Pre-built PV relationship dictionary.  Generated from database
        if not provided.
    script_relations : dict, optional
        Pre-built script relationship dictionary.  Generated from database if
        not provided.

    Returns
    -------
    nodes: dict
    edges: dict
    graph : graphviz.Digraph
    """
    node_id = 0
    edges = []
    nodes = {}

    if script_relations is None:
        if relations is None:
            relations = build_database_relations(database)

        script_relations = build_script_relations(
            database, relations,
            limit_to_records=limit_to_records,
        )

    limit_to_records = limit_to_records or []
    if graph is None:
        graph = AsyncDigraph(format="pdf")

    if font_name is not None:
        graph.attr("graph", dict(fontname=font_name))
        graph.attr("node", dict(fontname=font_name))
        graph.attr("edge", dict(fontname=font_name))

    if engine is not None:
        graph.engine = engine

    newline = '<br align="center"/>'

    def new_node(label, text=None):
        nonlocal node_id
        if label in nodes:
            return nodes[label]
        node_id += 1
        nodes[label] = dict(id=str(node_id), text=text or [], label=label)
        logger.debug("Created node %s", label)
        return node_id

    for script_a, script_a_relations in script_relations.items():
        new_node(script_a, text=[script_a])
        for script_b, _ in script_a_relations.items():
            if script_b in nodes:
                continue
            new_node(script_b, text=[script_b])

            inter_node = f"{script_a}<->{script_b}"
            new_node(
                inter_node,
                text=(
                    [f"<b>{script_a}</b>", ""]
                    + list(sorted(script_relations[script_a][script_b]))
                    + [""]
                    + [f"<b>{script_b}</b>", ""]
                    + list(sorted(script_relations[script_b][script_a]))
                ),
            )

            edges.append((script_a, inter_node, {}))
            edges.append((inter_node, script_b, {}))

    if not nodes:
        # No relationship found; at least show the records
        for rec_name in limit_to_records or []:
            try:
                new_node(rec_name)
            except KeyError:
                ...

    for name, node in sorted(nodes.items()):
        text = newline.join(node["text"])
        graph.node(
            node["id"],
            label="< {} >".format(text),
            shape="box3d" if name in limit_to_records else "rectangle",
            fillcolor="bisque" if name in limit_to_records else "white",
            style="filled",
        )

    # add all of the edges between graphs
    for src, dest, options in edges:
        graph.edge(nodes[src]["id"], nodes[dest]["id"], **options)

    return nodes, edges, graph
