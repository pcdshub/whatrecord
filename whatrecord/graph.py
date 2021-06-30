import ast
import collections
import html
import logging
from typing import Dict, List

import graphviz as gv
from whatrecord.common import LoadContext, PVRelations, dataclass
from whatrecord.db import RecordField, RecordInstance

logger = logging.getLogger(__name__)

# TODO: refactor this to not be graphviz-dependent; instead return node/link
# information in terms of dataclasses


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
    database: Dict[str, RecordInstance]
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

    Returns
    -------
    info : dict
        Such that: ``info[pv1][pv2] = (field1, field2, info)``
        And in reverse: ``info[pv2][pv1] = (field2, field1, info)``
    """
    warned = set()
    unset_ctx = (LoadContext("unset", 0), )
    by_record = collections.defaultdict(lambda: collections.defaultdict(list))

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
                field2 = rec2.fields[field2]
            else:
                rec2_name = rec2.name
                # TODO: this is not accurate; not all fields will be present in
                # the database unless set in the database file; perhaps these
                # should be populated from the dbd if necessary here?
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


def combine_relations(dest, *others):
    """Combine multiple script relations into one."""
    # TODO: this needs more work, it isn't as smart as it needs to be;
    # "unknown" field information needs updating
    for other in others:
        for rec1_name, rec1_items in other.items():
            if rec1_name not in dest:
                dest[rec1_name] = {}
            rec1_dict = dest[rec1_name]
            for rec2_name, rec2_items in rec1_items.items():
                if rec2_name not in rec1_dict:
                    rec1_dict[rec2_name] = []
                relation_list = rec1_dict[rec2_name]
                for relation in rec2_items:
                    relation_list.append(relation)


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


def build_script_relations(database, by_record, limit_to_records=None):
    if limit_to_records is None:
        record_items = by_record.items()
    else:
        record_items = [
            (name, database[name]) for name in limit_to_records
            if name in database
        ]

    by_script = collections.defaultdict(lambda: collections.defaultdict(set))
    for rec1_name, list_of_rec2s in record_items:
        rec1 = database.get(rec1_name, None)
        for rec2_name in list_of_rec2s:
            rec2 = database.get(rec2_name, None)

            rec1_file = rec1.context[0].name if rec1 else "unknown"
            rec2_file = rec2.context[0].name if rec2 else "unknown"

            if rec1_file != rec2_file:
                by_script[rec2_file][rec1_file].add(rec2_name)
                by_script[rec1_file][rec2_file].add(rec1_name)

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
        graph = gv.Digraph(format="pdf")

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
