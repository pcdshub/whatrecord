<template>
  <div id="contents">
    <div id="left" class="column">
      <div>
        <h3>Include unknown</h3>
        <InputSwitch
          v-model="include_unknown"
          :binary="true"
          @change="push_route"
        />
      </div>
      <div>
        <h3>Show records</h3>
        <InputSwitch
          v-model="show_records"
          :binary="true"
          @change="push_route"
        />
      </div>
      <div>
        <h3>Groups</h3>
        <DataTable
          id="groups"
          :value="groups"
          dataKey="name"
          v-model:selection="selected_groups"
          selectionMode="multiple"
          @rowSelect="push_route"
          :paginator="true"
          :rows="300"
          v-model:filters="group_filters"
          filterDisplay="row"
          :globalFilterFields="['iocs']"
        >
          <template #header>
            <div class="flex justify-content-between">
              <Button
                type="button"
                id="clear-filters"
                icon="pi pi-filter-slash"
                @click="clear_group_filters()"
              />
              <span class="p-input-icon-left">
                <i class="pi pi-search" />
                <InputText
                  v-model="group_filters['global'].value"
                  placeholder="Search"
                  id="filter-input"
                />
              </span>
            </div>
          </template>
          <Column field="iocs" header="IOC Names">
            <template #body="{ data }">
              <template v-for="ioc in data.iocs" :key="ioc">
                {{ ioc }}<br />
              </template>
            </template>
          </Column>
        </DataTable>
      </div>
    </div>
    <div class="column" id="graph_div" ref="graph_div">
      <GraphvizGraph
        :save_filename="graph_save_filename"
        :width="graph_width"
        :height="graph_height"
        :fit_graph="false"
        :dot_source="graph_dot_source"
      />
    </div>
    <div id="node_info" class="column hidden"></div>
  </div>
</template>

<script lang="ts">
import { defineComponent } from "vue";

import Button from "primevue/button";
import InputSwitch from "primevue/inputswitch";
import Column from "primevue/column";
import DataTable, { DataTableFilterMetaData } from "primevue/datatable";
import InputText from "primevue/inputtext";
import GraphvizGraph from "@/components/graphviz-graph.vue";
import { Relations } from "../types";
import { use_configured_store } from "../stores";
import { FilterMatchMode } from "primevue/api";

interface GraphvizNode {
  id: string;
  index: number;
  parent: string | null;
  children: GraphvizNode[];
  port: string | null;
}

interface GraphvizEdge {
  id: string;
  source_node: GraphvizNode;
  target_node: GraphvizNode;
  source_port: string | null;
  target_port: string | null;
  field_label: string;
}

interface GraphvizState {
  pv_to_node: Record<string, GraphvizNode>;
  ioc_to_node: Record<string, GraphvizNode>;
  nodes: GraphvizNode[];
  edges: GraphvizEdge[];
}

interface IOCGroup {
  name: string;
  iocs: string[];
}

interface Query {
  groups: string[];
  show_records: boolean;
  include_unknown: boolean;
}

function get_nodes(
  relations: Relations,
  include_unknown = false,
): GraphvizState {
  let pv_to_node: Record<string, GraphvizNode> = {};
  let ioc_to_node: Record<string, GraphvizNode> = {};
  let script_edges: Record<string, GraphvizEdge> = {};
  let edges = new Array<GraphvizEdge>();
  let node_index: number = 0;

  // Full relationship of IOC to PVs and per-record fields
  for (const [script_id, pvs] of Object.entries(relations.ioc_to_pvs)) {
    if (script_id === "unknown" && !include_unknown) {
      continue;
    }
    let script_node: GraphvizNode = {
      id: script_id,
      index: ++node_index,
      parent: null,
      children: [],
      port: null,
    };
    ioc_to_node[script_id] = script_node;

    for (const pv of pvs) {
      const pv_node: GraphvizNode = {
        id: pv,
        parent: script_node.id,
        index: ++node_index,
        port: `${script_node.index}:${fix_port_name(pv)}`,
        children: [],
      };
      pv_to_node[pv] = pv_node;
      script_node.children.push(pv_node);
    }
  }

  let graphed_fields = [];

  for (const [pv1, pv2s] of Object.entries(relations.pv_relations)) {
    const node1 = pv_to_node[pv1];
    const ioc1_node = ioc_to_node[node1?.parent ?? ""];
    if (node1 == null || ioc1_node == null) {
      continue;
    }

    // Full field info with context and all; may be too huge to serialize
    for (const [pv2, fields] of Object.entries(pv2s)) {
      const node2 = pv_to_node[pv2];
      const ioc2_node = ioc_to_node[node2?.parent ?? ""];
      if (pv1 === pv2 || node2 == null || ioc2_node == null) {
        continue;
      }

      for (const field_info of fields) {
        const [field1, field2, link_info] = field_info;
        const key1 = `${pv1}-${pv2}-${field1.name}-${field2.name}`;
        if (graphed_fields.indexOf(key1) >= 0) {
          continue;
        }
        const key2 = `${pv2}-${pv1}-${field2.name}-${field1.name}`;
        graphed_fields.push(key1);
        graphed_fields.push(key2);

        if (node1.parent != node2.parent) {
          const script_key = `${node1.parent}-${node2.parent}`;
          if (script_key in script_edges === false) {
            script_edges[script_key] = {
              id: script_key,
              source_node: ioc1_node,
              target_node: ioc2_node,
              source_port: null,
              target_port: null,
              field_label: "",
            };
          }
        }
        let field_label = `${field1.name}-${field2.name}`;
        if (link_info) {
          field_label += "\n" + link_info.join(", ");
        }
        edges.push({
          id: key1,
          source_node: ioc1_node,
          target_node: ioc2_node,
          source_port: node1.port + ":e",
          target_port: node2.port + ":w",
          field_label: field_label,
        });
      }
    }
  }

  return {
    pv_to_node: pv_to_node,
    ioc_to_node: ioc_to_node,
    nodes: Object.values(ioc_to_node),
    edges: Object.values(script_edges).concat(edges),
  };
}

function groups_from_relations(relations: Relations, include_unknown: boolean) {
  let groups = [];
  let saw = new Map<string, boolean>();
  if (!include_unknown) {
    saw.set("unknown", true);
  }
  for (const [ioc1, ioc2s_dict] of Object.entries(relations.script_relations)) {
    if (saw.has(ioc1)) {
      continue;
    }

    const ioc2s = Object.keys(ioc2s_dict);
    const name = `${ioc1},${ioc2s.join(",")}`;
    let group_iocs = [ioc1].concat(ioc2s);
    if (!include_unknown) {
      group_iocs = group_iocs.filter((item) => item != "unknown");
    }
    if (group_iocs.length > 1) {
      groups.push({
        name: name,
        iocs: group_iocs,
      });
    }
    for (const ioc of group_iocs) {
      saw.set(ioc, true);
    }
  }
  return groups;
}

function fix_port_name(port: string | null) {
  return port !== null ? port.replace(/:/g, "_") : null;
}

function create_ioc_dot_table(info: GraphvizNode, include_records = false) {
  let lines = ['<TABLE BORDER="0" CELLBORDER="0">'];

  function add_row({
    row,
    border = 1,
    port = null,
  }: {
    row: string[];
    border?: number;
    port?: string | null;
  }) {
    let tds = [];
    const border_text = border > 0 ? `BORDER="${border}" ` : "";
    const port_text = port != null ? `PORT="${port}" ` : "";
    for (const item of row) {
      tds.push(`<TD ${port_text} ${border_text}>${item}</TD>`);
    }
    const td_text = tds.join("\n");
    lines.push(`<TR>${td_text}</TR>`);
  }

  add_row({ row: [info.id], border: 0 });
  if (include_records) {
    for (const child of info.children ?? []) {
      add_row({ row: [child.id], port: fix_port_name(child.id) });
    }
  }
  lines.push("</TABLE>");
  return lines.join("\n");
}

function filter_elements(
  info: GraphvizState,
  ioc_list: string[],
  include_records: boolean,
) {
  if (!ioc_list) {
    return {
      nodes: [],
      edges: [],
    };
  }
  let nodes = new Array<GraphvizNode>();
  let edges = new Array<GraphvizEdge>();
  let records = new Map<string, boolean>();
  for (const node_info of info.nodes) {
    if (ioc_list.indexOf(node_info.id) >= 0) {
      nodes.push(node_info);
    } else if (
      include_records &&
      ioc_list.indexOf(node_info.parent ?? "") >= 0
    ) {
      nodes.push(node_info);
      records.set(node_info.id, true);
    }
  }
  for (const edge_info of info.edges) {
    if (
      nodes.indexOf(edge_info.source_node) >= 0 &&
      nodes.indexOf(edge_info.target_node) >= 0
    ) {
      edges.push(edge_info);
    }
  }
  return {
    nodes: nodes,
    edges: edges,
  };
}

function create_dot_source(
  info: GraphvizState,
  ioc_list: string[],
  include_records = false,
): string {
  const { nodes, edges } = filter_elements(info, ioc_list, include_records);
  if (nodes.length == 0) {
    console.debug("No IOCs after selection (or still loading)");
    return "";
  }

  let source_lines = ["digraph {"];

  for (const node of nodes) {
    const table = create_ioc_dot_table(node, include_records);
    source_lines.push(
      `${node.index} [label=< ${table} > fillcolor=white shape=rectangle style=filled]`,
    );
  }
  for (const edge of edges) {
    const source_id = edge.source_node.index;
    const target_id = edge.target_node.index;
    const source_port = edge.source_port;
    const target_port = edge.target_port;

    if (include_records) {
      if (source_port == null) {
        continue;
      }
      source_lines.push(
        `${source_port} -> ${target_port} `,
        // `[label=< ${edge.field_label} >]`
      );
    } else {
      if (source_port != null) {
        continue;
      }
      source_lines.push(
        `${source_id} -> ${target_id} [label=< ${edge.field_label} >]`,
      );
    }
  }
  source_lines.push("}");
  console.debug("graphviz source", source_lines.join("\n"));
  return source_lines.join("\n");
}

export default defineComponent({
  name: "PVRelationsView",
  components: {
    Button,
    Column,
    DataTable,
    GraphvizGraph,
    InputSwitch,
    InputText,
  },
  props: {},
  setup() {
    const store = use_configured_store();
    return { store };
  },
  data() {
    return {
      last_query: null as Query | null,
      full_relations: false,
      group_filters: {} as Record<string, DataTableFilterMetaData>,
      groups: [] as IOCGroup[],
      include_unknown: false,
      metadata: null,
      node_info: null as GraphvizState | null,
      selected_groups: [] as IOCGroup[],
      show_records: true,
      selected_record: null,
      shown_record: null as string | null,
      graph_dot_source: "",
      graph_height: 300,
      graph_width: 300,
    };
  },
  computed: {
    route_groups: function (): string[] {
      if (!this.$route.query.groups) {
        return [];
      }
      if (typeof this.$route.query.groups == "string") {
        return [this.$route.query.groups];
      }
      return this.$route.query.groups as string[]; // TODO/TS: is this cast OK?
    },
    graph_save_filename(): string {
      return this.selected_group_names.join(".") + ".svg";
    },
    selected_group_names(): string[] {
      let groups = [];
      for (const group of this.selected_groups) {
        groups.push(group.name);
      }
      return groups;
    },
    selected_ioc_list(): string[] {
      let iocs = [];
      for (const group of this.selected_groups) {
        for (const ioc of group.iocs) {
          iocs.push(ioc);
        }
      }
      return iocs;
    },
  },
  async created() {
    document.title = `whatrecord? PV Map`;
    this.init_group_filters();
    this.$watch(
      () => this.$route.query,
      (_to_params) => {
        this.from_params();
      },
    );
    await this.from_params();
  },
  async mounted() {
    const graph_div = this.$refs.graph_div as HTMLDivElement;
    this.graph_width = graph_div.clientWidth;
    this.graph_height = graph_div.clientHeight;

    const relations = this.store.pv_relations as Relations;
    if (relations === null) {
      await this.store.get_pv_relations();
    }
    await this.from_params();
  },
  methods: {
    async from_params() {
      const route_query = this.$route.query;
      const query: Query = {
        groups: this.route_groups as string[], // TODO: unable to get type checking
        show_records: route_query.show_records === "true",
        include_unknown: route_query.include_unknown === "true",
      };
      const record: string | null = route_query.record?.toString() ?? null;

      const relations = this.store.pv_relations as Relations;
      if (
        this.last_query != query &&
        Object.keys(relations?.pv_relations ?? {}).length > 0
      ) {
        this.last_query = query;

        this.show_records = query.show_records;
        this.include_unknown = query.include_unknown;
        this.groups = groups_from_relations(relations, query.include_unknown);
        let group_by_name: Record<string, IOCGroup> = {};
        for (const group of this.groups) {
          group_by_name[group.name] = group;
        }
        this.selected_groups = [];
        for (const group of query.groups) {
          if (group in group_by_name) {
            this.selected_groups.push(group_by_name[group]);
          }
        }

        this.node_info = get_nodes(relations, query.include_unknown);

        try {
          this.graph_dot_source = create_dot_source(
            this.node_info,
            this.selected_ioc_list as string[],
            query.show_records,
          );
        } catch (error) {
          console.error("Failed to update plot", error);
          this.graph_dot_source = "digraph { sorry you encountered a bug }";
        }
      }

      if (record && this.shown_record != record) {
        this.shown_record = record;
      }
    },
    push_route() {
      this.$router.push({
        query: {
          record: this.selected_record,
          show_records: this.show_records.toString(),
          include_unknown: this.include_unknown.toString(),
          groups: this.selected_group_names,
          global_filter: this.group_filters["global"].value,
        },
      });
    },

    clear_group_filters() {
      this.init_group_filters();
    },

    init_group_filters() {
      this.group_filters = {
        global: {
          value: null,
          matchMode: FilterMatchMode.CONTAINS,
        },
        iocs: {
          value: null,
          matchMode: FilterMatchMode.CONTAINS,
        },
      };
    },
  },
});
</script>

<style scoped>
#contents {
  display: flex;
  flex-direction: row;
  height: 94vh;
  justify-content: flex-start;
  overflow-y: scroll;
}

.column {
  display: flex;
  flex-direction: column;
  overflow-y: scroll;
}

#left {
  min-width: 17vw;
  max-width: 17vw;
  max-height: 97vh;
}

#graph_div {
  height: 100%;
  width: 100%;
}

#clear-filters {
  padding-left: 0.5em;
  padding-right: 0.5em;
  margin-left: 0.5em;
  margin-right: 0.5em;
}

#filter-input {
  width: 100%;
}
</style>
