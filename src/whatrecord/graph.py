import collections
import dataclasses
import html
import logging
from typing import Tuple

import graphviz as gv

# from .db import RecordField, RecordInstance
from whatrecord.db import RecordField, RecordInstance

logger = logging.getLogger(__name__)

link_types = {"DBF_INLINK", "DBF_OUTLINK", "DBF_FWDLINK"}


@dataclasses.dataclass
class LinkInfo:
    record1: RecordInstance
    field1: RecordField
    record2: RecordInstance
    field2: RecordField
    info: str


def get_link_information(link_str: str) -> Tuple[str, str]:
    """Get link information from a DBF_{IN,OUT,FWD}LINK value."""
    if " " in link_str:
        # strip off PP/MS/etc (TODO might be useful later)
        link_str, additional_info = link_str.split(" ", 1)
    else:
        additional_info = ""

    if link_str.startswith("@"):
        # TODO asyn/device links
        raise ValueError("asyn link")
    if not link_str:
        raise ValueError("empty link")

    if link_str.isnumeric():
        # 0 or 1 usually and not a string
        raise ValueError("integral link")

    try:
        float(link_str)
    except Exception:
        # Good, we don't want a float
        ...
    else:
        raise ValueError("float link")

    return link_str, tuple(additional_info.split(" "))


def find_record_links(database, starting_records, check_all=True):
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

    Yields
    -------
    link_info : LinkInfo
        Link info
    """
    checked = []

    def get_links(rec):
        for field in rec.get_fields_of_type(*link_types):
            try:
                link, info = get_link_information(field.value)
            except ValueError:
                continue
            yield field, link, info

    relations = collections.defaultdict(lambda: collections.defaultdict(list))
    for rec1 in database.values():
        for field1, link, info in get_links(rec1):
            if "." in link:
                link, field2 = link.split(".")
            elif field1.name == "FLNK":
                field2 = "PROC"
            else:
                field2 = "VAL"

            rec2 = database.get(link, None)
            if rec2 is None:
                logger.warning("Linked record not in database: %s", link)
            else:
                if field2 in rec2.fields:
                    field2 = rec2.fields[field2]
                else:
                    field2 = RecordField(
                        dtype="unknown", name=field2, value="", context=("unset:0",)
                    )

                relations[rec1.name][rec2.name].append((field1, field2, info))
                relations[rec2.name][rec1.name].append((field2, field1, info))

    records_to_check = list(starting_records)

    while records_to_check:
        rec1 = database[records_to_check.pop()]
        checked.append(rec1.name)
        logger.debug("--- record %s ---", rec1.name)

        for rec2_name, fields in relations[rec1.name].items():
            if rec2_name in checked:
                continue

            rec2 = database[rec2_name]
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
    field_format="{field:>4s}: {value!r}",
    sort_fields=True,
    text_format=None,
    show_empty=False,
    font_name="Courier",
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

    Returns
    -------
    graph : graphviz.Graph
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

    if text_format is None:
        text_format = """<b> {header} </b> <br/><br align="left"/>{field_lines}"""

    # graph.attr("node", {"shape": "record"})

    for li in find_record_links(database, starting_records):
        for (rec, attr) in ((li.record1, li.field1), (li.record2, li.field2)):
            if rec.name not in nodes:
                node_id += 1
                nodes[rec.name] = dict(id=str(node_id), text=[], record=rec)
                # graph.node(nodes[rec.name], label=attr)
                logger.debug("Created node %s.%s", rec.name, attr)

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
            edge_kw["style"] = "bold"

        if any(item in li.info for item in {"MS", "MSS", "MSI"}):
            edge_kw["color"] = "red"

        src_id, dest_id = src["id"], dest["id"]
        if (src_id, dest_id) not in existing_edges:
            edge_kw["label"] = f"{li.field1.name}/{li.field2.name}"
            if li.info:
                edge_kw["label"] += f"\n{' '.join(li.info)}"
            edges.append((src_id, dest_id, edge_kw))
            existing_edges.add((src_id, dest_id))

    for _, node in sorted(nodes.items()):
        field_lines = node["text"]
        if sort_fields:
            field_lines.sort()

        if field_lines:
            field_lines.append("")
            field_lines = (html.escape(line, quote=False) for line in field_lines)
        else:
            field_lines = []

        rec = node["record"]
        header = header_format.format(rtype=rec.record_type, name=rec.name)
        text = text_format.format(
            header=html.escape(header, quote=False),
            field_lines='<br align="left"/>'.join(field_lines),
        )
        graph.node(
            node["id"],
            label="< {} >".format(text),
            shape="box3d" if rec.name in starting_records else "rectangle",
            fillcolor="bisque" if rec.name in starting_records else "white",
        )

    # add all of the edges between graphs
    for src, dest, options in edges:
        graph.edge(src, dest, **options)

    return graph
