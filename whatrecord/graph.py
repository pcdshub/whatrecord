import ast
import collections
import copy
import dataclasses
import html
import logging
import textwrap
from dataclasses import dataclass
from typing import Any, ClassVar, Dict, Generator, List, Optional, Tuple, Union

import graphviz as gv

from .common import (FullLoadContext, LoadContext, PVRelations,
                     ScriptPVRelations)
from .db import Database, RecordField, RecordInstance, RecordType
from .gv_compat import AsyncDigraph

logger = logging.getLogger(__name__)

# TODO: refactor this to not be graphviz-dependent; instead return node/link
# information in terms of dataclasses


@dataclass()
class GraphNode:
    #: The integer ID of the node
    id: str
    #: The node label
    label: str
    #: The text to show in the node
    text: str
    #: Options to pass to graphviz.
    options: dict = dataclasses.field(default_factory=dict)
    #: Highlight the node in the graph?
    highlighted: bool = False
    #: User-specified metadata
    metadata: Dict[str, Any] = dataclasses.field(default_factory=dict)

    def add_text_line(self, line: str, delimiter: str = "\n", only_unique: bool = True):
        """
        Add a line of text to the node.

        Parameters
        ----------
        line : str
            The line to add.

        delimiter : str, optional
            The between-line delimiter.

        only_unique : bool, optional
            Only add unique lines to the text.
        """
        if not self.text.strip():
            self.text = line
        elif not only_unique or line not in self.text:
            self.text = delimiter.join((self.text, line))

    def __hash__(self):
        return hash(self.id)


@dataclass
class GraphEdge:
    #: The source node.
    source: GraphNode
    #: The destination node.
    destination: GraphNode
    #: The source node.
    source_port: Optional[str] = None
    #: The destination node.
    destination_port: Optional[str] = None
    #: Options to pass to graphviz.
    options: dict = dataclasses.field(default_factory=dict)

    @property
    def source_with_port(self) -> str:
        """Source name including the port name, for graphviz."""
        if self.source_port is None:
            return self.source.id
        return f"{self.source.id}:{self.source_port}_value:e"

    @property
    def destination_with_port(self) -> str:
        """Destination name including the port name, for graphviz."""
        if self.destination_port is None:
            return self.destination.id
        return f"{self.destination.id}:{self.destination_port}_name:w"


class _GraphHelper:
    """
    A base class for helping build graphviz digraphs.
    """

    shapes: Tuple[str, str] = ("rectangle", "box3d")
    fill_colors: Tuple[str, str] = ("white", "bisque")
    newline: str = '<br align="left"/>'
    nodes: Dict[str, GraphNode]
    edges: List[GraphEdge]

    def __init__(self):
        self._node_id = 0
        self.nodes = {}
        self.edges = []

    @property
    def edge_pairs(self) -> Generator[Tuple[GraphNode, GraphNode], None, None]:
        for edge in self.edges:
            yield (edge.source, edge.destination)

    def get_node(
        self, label: str, text: Optional[str] = None
    ) -> GraphNode:
        """Create a new node in the graph."""
        if label not in self.nodes:
            self._node_id += 1
            self.nodes[label] = GraphNode(
                id=str(self._node_id),
                text=text or label,
                label=label
            )
            logger.debug("Created node %s", label)

        if text and text.strip():
            self.nodes[label].add_text_line(text)

        return self.nodes[label]

    def add_edge(
        self,
        source: str,
        destination: str,
        allow_dupes: bool = False,
        source_port: Optional[str] = None,
        dest_port: Optional[str] = None,
        **options
    ) -> GraphEdge:
        """Create a new edge in the graph."""
        edge = GraphEdge(
            self.get_node(source),
            self.get_node(destination),
            source_port=source_port,
            destination_port=dest_port,
            options=options
        )
        if edge in self.edges and not allow_dupes:
            return self.edges[self.edges.index(edge)]
        self.edges.append(edge)
        return edge

    def _ready_for_digraph(self, graph: gv.Digraph):
        """Hook when the user calls ``to_digraph``."""
        raise NotImplementedError()

    def to_digraph(
        self,
        graph: Optional[gv.Digraph] = None,
        engine: str = "dot",
        font_name: Optional[str] = "Courier",
        format: str = "pdf",
    ) -> gv.Digraph:
        """
        Create a graphviz digraph.

        Parameters
        ----------
        graph : graphviz.Graph, optional
            Graph instance to use.  New one created if not specified.
        engine : str, optional
            Graphviz engine (dot, fdp, etc).
        font_name : str, optional
            Font name to use for all nodes and edges.
        format :
            The output format used for rendering (``'pdf'``, ``'png'``, ...).
        """
        graph = graph or AsyncDigraph(format=format)

        # Call the subclass hook:
        self._ready_for_digraph(graph)

        if engine is not None:
            graph.engine = engine

        if font_name is not None:
            graph.attr("graph", fontname=font_name)
            graph.attr("node", fontname=font_name)
            graph.attr("edge", fontname=font_name)

        for node in self.nodes.values():
            text = self.newline.join(node.text.splitlines())
            graph.node(
                node.id,
                label=f"< {text} >",
                shape=self.shapes[node.highlighted],
                fillcolor=self.fill_colors[node.highlighted],
                style="filled",
                **node.options
            )

        # add all of the edges between graphs
        for edge in self.edges:
            graph.edge(
                edge.source_with_port,
                edge.destination_with_port,
                **edge.options
            )
        return graph

    @staticmethod
    def clean_code(obj):
        """Clean C-like code for graphviz."""
        code = str(obj or "").strip("{}")
        return html.escape(textwrap.dedent(code).strip(" \n"))


@dataclass
class LinkInfo:
    record1: RecordInstance
    field1: RecordField
    record2: RecordInstance
    field2: RecordField
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


def _get_links_for_record(
    record: RecordInstance, record_types: Optional[Dict[str, RecordType]] = None
) -> Generator[Tuple[RecordField, str, List[str]], None, None]:
    """
    Get links for the provided record, referring back to the record_types dict if necessary.
    """
    if record.has_dbd_info:
        yield from record.get_links()
    elif record_types is not None:
        rec1_rtype = record_types.get(record.record_type, None)
        if rec1_rtype is not None:
            yield from rec1_rtype.get_links_for_record(record)


_unset_ctx: FullLoadContext = (LoadContext("unknown", 0), )


def _field_from_record_relation(
    record: Optional[RecordInstance],
    field_name: str,
    link_text: str,
    record_types: Dict[str, RecordType]
) -> Optional[RecordField]:
    """
    Create a RecordField instance based on what we know, given the parameters.

    Parameters
    ----------
    record : RecordInstance or None
        An (optional) record instance, if available in the database.

    field_name : str
        A field name for the record (field_name).

    link_text : str, optional
        The link text - likely the record name - referring to ``record``.

    record_types : dict, optional
        Record type information from a database definition.
    """
    if record is None:
        # Case 1: The linked record is *not* in the database.

        if not is_supported_link(link_text):
            return None

        return RecordField(
            dtype="unknown",
            name=field_name,
            value="(unknown-record)",
            context=_unset_ctx,
        )

    if field_name in record.fields:
        # Case 2: The linked record is in the database and has a
        # recognized field name.
        return copy.deepcopy(record.fields[field_name])

    # Case 3: The linked record is in the database but does not
    # have a recognized field name.
    dbd_record_type = record_types.get(record.record_type, None)
    if dbd_record_type is None:
        # Record type not in the database?
        return RecordField(
            dtype="invalid",
            name=field_name,
            value="(invalid-record-type)",
            context=_unset_ctx,
        )

    if field_name not in dbd_record_type.fields:
        # Field name invalid
        return RecordField(
            dtype="invalid",
            name=field_name,
            value="(invalid-field)",
            context=_unset_ctx,
        )

    # Record and field found in provided record_types
    dbd_record_field = dbd_record_type.fields[field_name]
    return RecordField(
        dtype=dbd_record_field.type,
        name=field_name,
        value="",
        context=dbd_record_field.context,
    )


def build_database_relations(
    database: Dict[str, RecordInstance],
    record_types: Optional[Dict[str, RecordType]] = None,
    aliases: Optional[Dict[str, str]] = None,
    version: int = 3,
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
        If not specified, the whatrecord-vendored database definition files
        will be used.

    version : int, optional
        Use the old V3 style or new V3 style database grammar by specifying
        3 or 4, respectively.  Defaults to 3.

    Returns
    -------
    info : dict
        Such that: ``info[pv1][pv2] = (field1, field2, info)``
        And in reverse: ``info[pv2][pv1] = (field2, field1, info)``
    """
    if not record_types:
        dbd = Database.from_vendored_dbd(version=version)
        record_types = dbd.record_types

    aliases = aliases or {}
    warned = set()
    by_record = collections.defaultdict(lambda: collections.defaultdict(list))

    for rec1 in database.values():
        rec1_rtype = record_types.get(rec1.record_type, None)
        for field1, link, info in _get_links_for_record(
            rec1, record_types=record_types
        ):
            field1 = copy.deepcopy(field1)
            # field1.context = rec1.context[:1] + field1.context

            if not rec1.has_dbd_info and rec1_rtype:
                field1.update_from_record_type(rec1_rtype)

            if "." in link:
                link, field2_name = link.split(".", 1)
            elif field1.name == "FLNK":
                field2_name = "PROC"
            else:
                field2_name = "VAL"

            rec2_name = aliases.get(link, link)
            rec2 = database.get(rec2_name, None)

            field2 = _field_from_record_relation(
                record=rec2,
                field_name=field2_name,
                link_text=link,
                record_types=record_types,
            )

            if field2 is None:
                continue

            if rec2 is None:
                warned.add(rec2_name)
                logger.debug(
                    "Linked record from %s.%s not in database: %s",
                    rec1.name, field1.name, rec2_name
                )
            else:
                # We may have updated information about the record field;
                # but it's possible this is entirely unnecessary (TODO)
                rec2_type = record_types.get(rec2.record_type, None)
                if rec2_type is not None:
                    field2.update_from_record_type(rec2_type)

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


def find_record_links(
    database: Dict[str, RecordInstance],
    starting_records: List[str],
    relations: Optional[PVRelations] = None,
    record_types: Optional[Dict[str, RecordType]] = None,
) -> Generator[LinkInfo, None, None]:
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

    record_types : dict, optional
        The database definitions to use for fields that are not defined in the
        database file.  Dictionary of record type name to RecordType.

    Yields
    ------
    link_info : LinkInfo
        Link info
    """
    checked = []

    if relations is None:
        relations = build_database_relations(database, record_types=record_types)

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


class RecordLinkGraph(_GraphHelper):
    """Record link graph."""
    # TODO: create node and color when not in database?

    database: Database
    starting_records: List[str]
    newline: str = '\n'
    header_format: str = '{name} ({rtype})'
    field_format: str = '{field}: "{value}"'
    text_format: str = (
        """
        <TABLE BORDER="0" CELLBORDER="0">
        <TR>
            <TD>{rtype}</TD>
            <TD><b>{name}</b></TD>
        </TR>
        {field_lines}
        </TABLE>
        """.strip()
    )
    sort_fields: bool
    show_empty: bool
    relations: Optional[PVRelations]
    record_types: Dict[str, RecordType]
    default_edge_kwargs: Dict[str, str] = {
        "style": "solid",
    }

    edge_kwargs: ClassVar[Dict[str, Dict[str, str]]] = {
        "style": {
            "PP": "bold",
            "CPP": "bold",
            "CP": "bold",
        },
        # "color": {
        #     "MS": "",
        #     "MSS": "",
        #     "MSI": "",
        # }
    }

    # Edge colors to cycle through: black is reserved for FLNK.
    edge_colors: ClassVar[List[str]] = textwrap.dedent(
        """\
        brown
        darkblue
        darkcyan
        darkgreen
        darkmagenta
        darkred
        olive
        """.rstrip()
    ).split()

    def __init__(
        self,
        database: Optional[Union[Database, Dict[str, RecordInstance]]] = None,
        starting_records: Optional[List[str]] = None,
        header_format: Optional[str] = None,
        field_format: Optional[str] = None,
        text_format: Optional[str] = None,
        sort_fields: bool = True,
        show_empty: bool = True,
        relations: Optional[PVRelations] = None,
        record_types: Optional[Dict[str, RecordType]] = None,
    ):
        super().__init__()
        self.database = Database(record_types=dict(record_types or {}))
        self.starting_records = starting_records or []
        self.header_format = header_format or type(self).header_format
        self.field_format = field_format or type(self).field_format
        self.text_format = text_format or type(self).text_format
        self.sort_fields = sort_fields
        self.show_empty = show_empty
        self.relations = relations

        if database is not None:
            self.add_database(database)

    def get_node(
        self, label: str, text: Optional[str] = None
    ) -> GraphNode:
        node = super().get_node(label, text=text)
        if not node.metadata:
            node.metadata["fields"] = {}
        return node

    def add_database(self, database: Union[Dict[str, RecordInstance], Database]):
        """Add records from the given database to the graph."""
        if isinstance(database, Database):
            self.database.append(database)
        else:
            for record in database.values():
                self.database.add_or_update_record(record)

        if not self.relations:
            self.relations = build_database_relations(
                self.database.records, record_types=self.database.record_types
            )

        edge_color_idx = 0
        for li in find_record_links(
            self.database.records, self.starting_records, relations=self.relations
        ):
            src = self.get_node(li.record1.name, text=" ")
            dest = self.get_node(li.record2.name, text=" ")

            for field, node in [(li.field1, src), (li.field2, dest)]:
                if field.name == "PROC":
                    ...
                elif field.value or self.show_empty:
                    node.metadata["fields"][field.name] = textwrap.dedent(
                        f"""\
                        <TR>
                            <TD PORT="{field.name}_name" BORDER="1">
                                <B>{field.name}</B>
                            </TD>
                            <TD PORT="{field.name}_value" BORDER="1">
                                {field.value}
                            </TD>
                        </TR>
                        """
                    ).rstrip()

            if li.field1.dtype == "DBF_INLINK":
                src, dest = dest, src
                li.field1, li.field2 = li.field2, li.field1

            logger.debug("New edge %s -> %s", src, dest)

            edge_kw = dict(self.default_edge_kwargs)
            for key, to_find in self.edge_kwargs.items():
                for match, value in to_find.items():
                    if match in li.info:
                        edge_kw[key] = value
                        break

            if (src, dest) not in set(self.edge_pairs):
                if "DBF_FWDLINK" in (li.field1.dtype, li.field2.dtype):
                    edge_kw["taillabel"] = "FLNK"
                    self.add_edge(src.label, dest.label, color="black", **edge_kw)
                else:
                    # edge_kw["taillabel"] = f"{li.field1.name}"
                    # edge_kw["headlabel"] = f"{li.field2.name}"
                    if li.info:
                        edge_kw["xlabel"] = f"\n{' '.join(li.info)}"

                    edge_color_idx += 1
                    color = self.edge_colors[edge_color_idx % len(self.edge_colors)]

                    self.add_edge(
                        f"{src.label}",
                        f"{dest.label}",
                        source_port=li.field1.name,
                        dest_port=li.field2.name,
                        color=color,
                        **edge_kw,
                    )

        if not self.nodes:
            # No relationship found; at least show the records
            for rec_name in self.starting_records:
                if rec_name in self.database.records:
                    self.get_node(rec_name)

        for node in self.nodes.values():
            # if self.sort_fields:
            #     node.text = "\n".join(sorted(node.text.splitlines()))
            rec = self.database.records[node.label]
            if rec.aliases:
                sub_header = html.escape(f"\nAlias: {', '.join(rec.aliases)}")
                sub_header = f"""<TR><TD>{sub_header}</TD></TR>"""
            else:
                sub_header = ""

            fields = list(sorted(node.metadata["fields"].items()))
            field_text = "\n".join(text for _, text in fields)
            node.text = self.text_format.format(
                rtype=html.escape(rec.record_type),
                name=html.escape(rec.name),
                field_lines=(sub_header + field_text).strip(),
            )

    @property
    def graphed_records(self) -> List[str]:
        """All graphed record names (i.e., node labels)."""
        return [
            node.label
            for node in self.nodes.values()
        ]

    def _ready_for_digraph(self, graph: gv.Digraph):
        """Hook when the user calls ``to_digraph``."""
        all_match = set(self.graphed_records) <= set(self.starting_records)
        for node in self.nodes.values():
            node.highlighted = (
                not all_match and
                node.label in self.starting_records
            )


def graph_links(
    database: Union[Database, Dict[str, RecordInstance]],
    starting_records: List[str],
    header_format: Optional[str] = None,
    field_format: Optional[str] = None,
    text_format: Optional[str] = None,
    sort_fields: bool = True,
    show_empty: bool = True,
    relations: Optional[PVRelations] = None,
    record_types: Optional[Dict[str, RecordType]] = None,
) -> RecordLinkGraph:
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
    record_types : dict, optional
        The database definitions to use for fields that are not defined in the
        database file.  Dictionary of record type name to RecordType.  Only
        used for determining script relations if not specified.

    Returns
    -------
    graph : RecordLinkGraph
    """

    return RecordLinkGraph(
        database=database,
        starting_records=starting_records,
        header_format=header_format,
        field_format=field_format,
        text_format=text_format,
        sort_fields=sort_fields,
        show_empty=show_empty,
        relations=relations,
        record_types=record_types,
    )


def build_script_relations(
    database: Dict[str, RecordInstance],
    by_record: PVRelations,
    limit_to_records: Optional[List[str]] = None
) -> ScriptPVRelations:
    """
    Build a relational map of IOCs that include inter-IOC PV relationships.

    Parameters
    ----------
    database : Dict[str, RecordInstance]
        The full composite database.
    by_record : PVRelations
        PV relationships, as generated by ``build_database_relations``.
        This is a mapping of PV1 to {"PV2": [FieldRelation, ...]}.
    limit_to_records : List[str], optional
        Limit the relationships to only the provided records.  If not set,
        defaults to all records in the composite database.

    Returns
    -------
    ScriptPVRelations
    """
    if not limit_to_records:
        record_items = by_record.items()
    else:
        record_items = [
            (name, by_record[name]) for name in limit_to_records
            if name in by_record
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
            if owner1 != owner2:
                by_script[owner2][owner1].add(rec2_name)
                by_script[owner1][owner2].add(rec1_name)

    return {
        owner1: {
            owner2: list(items)
            for owner2, items in owner2s.items()
        }
        for owner1, owner2s in by_script.items()
    }


class ScriptLinkGraph(_GraphHelper):
    """
    Script link graph (i.e., inter-IOC record links).

    Parameters
    ----------
    database : dict
        Dictionary of record name to record instance.
    starting_records : list of str
        Record names
    sort_fields : bool, optional
        Sort list of fields
    show_empty : bool, optional
        Show empty fields
    relations : dict, optional
        Pre-built PV relationship dictionary.  Generated from database
        if not provided.
    script_relations : dict, optional
        Pre-built script relationship dictionary.  Generated from database if
        not provided.
    record_types : dict, optional
        The database definitions to use for fields that are not defined in the
        database file.  Dictionary of record type name to RecordType.  Only
        used for determining script relations if not specified.
    """
    # TODO: create node and color when not in database?

    newline: str = '<br align="center"/>'

    def __init__(
        self,
        database: Optional[Union[Database, Dict[str, RecordInstance]]] = None,
        limit_to_records: Optional[List[str]] = None,
        relations: Optional[PVRelations] = None,
        script_relations: Optional[ScriptPVRelations] = None,
        record_types: Optional[Dict[str, RecordType]] = None,
    ):
        super().__init__()
        self.database = Database(record_types=dict(record_types or {}))
        self.limit_to_records = limit_to_records or []
        self.relations = relations
        self.script_relations = script_relations

        if database is not None:
            self.add_database(database)

    def add_database(self, database: Union[Dict[str, RecordInstance], Database]):
        """Add records from the given database to the graph."""
        if isinstance(database, Database):
            self.database.append(database)
        else:
            for record in database.values():
                self.database.add_or_update_record(record)

        # if not self.script_relations:
        self.relations = build_database_relations(
            self.database.records,
            record_types=self.database.record_types,
        )

        self.script_relations = build_script_relations(
            database=self.database.records,
            by_record=self.relations,
            limit_to_records=self.limit_to_records,
        )

        for script_a, script_a_relations in self.script_relations.items():
            self.get_node(script_a, text=script_a)
            for script_b in script_a_relations:
                if script_b in self.nodes:
                    continue
                self.get_node(script_b, text=script_b)

                inter_lines = (
                    [f"<b>{script_a}</b>", ""]
                    + list(sorted(self.script_relations[script_a][script_b]))
                    + [""]
                    + [f"<b>{script_b}</b>", ""]
                    + list(sorted(self.script_relations[script_b][script_a]))
                )
                inter_node = f"{script_a}<->{script_b}"
                self.get_node(inter_node, text="\n".join(inter_lines))
                self.add_edge(script_a, inter_node)
                self.add_edge(inter_node, script_b)

        if not self.nodes:
            # No relationship found; at least show the records
            for rec_name in self.limit_to_records or []:
                if rec_name in self.database.records:
                    self.get_node(rec_name)

    def _ready_for_digraph(self, graph: gv.Digraph):
        """Hook when the user calls ``to_digraph``."""
        for node in self.nodes.values():
            node.highlighted = node.label in self.limit_to_records


def graph_script_relations(
    database: Dict[str, RecordInstance],
    limit_to_records: Optional[List[str]] = None,
    relations: Optional[PVRelations] = None,
    script_relations: Optional[ScriptPVRelations] = None,
    record_types: Optional[Dict[str, RecordType]] = None,
) -> ScriptLinkGraph:
    """
    Create a graphviz digraph of script links (i.e., inter-IOC record links).

    Parameters
    ----------
    database : dict
        Dictionary of record name to record instance.
    starting_records : list of str
        Record names
    relations : dict, optional
        Pre-built PV relationship dictionary.  Generated from database
        if not provided.
    script_relations : dict, optional
        Pre-built script relationship dictionary.  Generated from database if
        not provided.
    record_types : dict, optional
        The database definitions to use for fields that are not defined in the
        database file.  Dictionary of record type name to RecordType.  Only
        used for determining script relations if not specified.

    Returns
    -------
    graph : ScriptLinkGraph
    """
    return ScriptLinkGraph(
        database=database,
        limit_to_records=limit_to_records,
        relations=relations,
        script_relations=script_relations,
        record_types=record_types,
    )
