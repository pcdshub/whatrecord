import collections
import html
import logging
from typing import DefaultDict, Dict, Tuple

import graphviz as gv

from .common import LoadContext, dataclass
from .db import RecordField, RecordInstance

logger = logging.getLogger(__name__)

# TODO: refactor this to not be graphviz-dependent; instead return node/link
# information in terms of dataclasses


@dataclass
class LinkInfo:
    record1: RecordInstance
    field1: RecordField
    record2: RecordInstance
    field2: RecordField
    info: Tuple[str, ...]


def build_database_relations(
    database: Dict[str, RecordInstance]
) -> Dict[str, DefaultDict[str, Tuple[RecordField, RecordField, Tuple[str, ...]]]]:
    """
    Build a dictionary of PV relationships.

    This should not be called often for large databases, as it makes no attempt
    to be computationally efficient.  For repeated usage, cache the result
    of this function and reuse it in future calls to ``graph_links`` and such.

    Parameters
    ----------
    database : dict
        Dictionary of record name to record instance.

    Returns
    -------
    info : dict
        Such that: ``info[pv1][pv2] = (field1, field2, info)``
        And in reverse: ``info[pv2][pv1] = (field2, field1, info)``
    """
    warned = set()
    unset_ctx = (LoadContext("unset", 0).freeze(), )
    relations = collections.defaultdict(lambda: collections.defaultdict(list))
    for rec1 in database.values():
        for field1, link, info in rec1.get_links():
            if "." in link:
                link, field2 = link.split(".")
            elif field1.name == "FLNK":
                field2 = "PROC"
            else:
                field2 = "VAL"

            rec2 = database.get(link, None)
            if rec2 is None:
                # TODO: switch to debug; this will be expensive later
                # TODO: check for constant links, ignore card/slot syntax, etc
                if link.startswith("#") or link in warned:
                    ...
                else:
                    logger.warning("Linked record not in database: %s", link)
                    warned.add(link)
            else:
                if field2 in rec2.fields:
                    field2 = rec2.fields[field2]
                else:
                    field2 = RecordField(
                        dtype="unknown",
                        name=field2,
                        value="",
                        context=unset_ctx,
                    )

                relations[rec1.name][rec2.name].append((field1, field2, info))
                relations[rec2.name][rec1.name].append((field2, field1, info))

    return dict(relations)


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
    graph : graphviz.Digraph
    """
    node_id = 0
    edges = []
    nodes = {}
    existing_edges = set()

    if graph is None:
        graph = gv.Digraph(format="pdf")

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
        text = text_format.format(
            header=html.escape(header, quote=False),
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
