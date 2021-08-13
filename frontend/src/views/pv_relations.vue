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
            <div class="p-d-flex p-jc-between">
              <Button
                type="button"
                icon="pi pi-filter-slash"
                label="Clear"
                class="p-button-outlined"
                @click="clear_group_filters()"
              />
              <span class="p-input-icon-left">
                <i class="pi pi-search" />
                <InputText
                  v-model="group_filters['global'].value"
                  placeholder="Search"
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
    <div id="graph" class="column"></div>
    <div id="node_info" class="column hidden"></div>
  </div>
</template>

<script>
import { mapState } from "vuex";
const axios = require("axios").default;

import Button from "primevue/button";
import InputSwitch from "primevue/inputswitch";
import Column from "primevue/column";
import DataTable from "primevue/datatable";
import InputText from "primevue/inputtext";
import { FilterMatchMode } from "primevue/api";

import cytoscape from "cytoscape";
import fcose from "cytoscape-fcose";

cytoscape.use(fcose);

function get_simple_nodes(
  relations,
  include_unknown = false,
  include_records = false
) {
  let pv_to_node = {};
  let ioc_to_node = {};
  let script_edges = {};
  for (const [ioc1, ioc2s] of Object.entries(relations.script_relations)) {
    if (ioc1 === "unknown" && !include_unknown) {
      continue;
    }
    if (ioc1 in ioc_to_node === false) {
      let script_node = {
        data: {
          id: ioc1,
        },
        classes: ["script"],
      };
      ioc_to_node[ioc1] = script_node;
    }
    for (const [ioc2, pvs] of Object.entries(ioc2s)) {
      if (ioc2 === "unknown" && !include_unknown) {
        continue;
      }
      const script_key = `${ioc1}-${ioc2}`;
      if (script_key in script_edges === false) {
        script_edges[script_key] = {
          data: {
            id: script_key,
            source: ioc1,
            target: ioc2,
            field_label: "",
          },
        };
      }
      if (include_records) {
        for (const pv of pvs) {
          if (pv in pv_to_node === false) {
            const pv_node = {
              data: {
                id: pv,
                parent: ioc2,
                weight: 1,
              },
              classes: ["pv"],
            };
            pv_to_node[pv] = pv_node;
          }
        }
      }
    }
  }

  return {
    pv_to_node: pv_to_node,
    ioc_to_node: ioc_to_node,
    script_edges: script_edges,
    edges: [],
    all_nodes: Object.values(ioc_to_node).concat(Object.values(pv_to_node)),
    all_edges: Object.values(script_edges),
  };
}

function get_all_nodes(relations, include_unknown = false) {
  // This may be defunct
  let pv_to_node = {};
  let ioc_to_node = {};
  let script_edges = {};
  let edges = [];
  // Full relationship of IOC to PVs and per-record fields
  for (const [script_id, pvs] of Object.entries(relations.ioc_to_pvs)) {
    if (script_id === "unknown" && !include_unknown) {
      continue;
    }
    let script_node = {
      data: {
        id: script_id,
        weight: 2,
      },
      classes: ["script"],
    };
    ioc_to_node[script_id] = script_node;
    for (const pv of pvs) {
      const pv_node = {
        data: {
          id: pv,
          parent: script_id,
          weight: 1,
        },
        classes: ["pv"],
      };
      pv_to_node[pv] = pv_node;
    }
  }

  let graphed_fields = [];

  for (const [pv1, pv2s] of Object.entries(relations.pv_relations)) {
    const node1 = pv_to_node[pv1];
    // Full field info with context and all; may be too huge to serialize
    for (const [pv2, fields] of Object.entries(pv2s)) {
      if (pv1 === pv2) {
        continue;
      }
      const node2 = pv_to_node[pv2];
      for (const field_info of fields) {
        const field1 = field_info.fields[0];
        const field2 = field_info.fields[1];
        const link_info = field_info.info;
        const key1 = `${pv1}-${pv2}-${field1.name}-${field2.name}`;
        if (graphed_fields.indexOf(key1) >= 0) {
          continue;
        }
        const key2 = `${pv2}-${pv1}-${field2.name}-${field1.name}`;
        graphed_fields.push(key1);
        graphed_fields.push(key2);

        if (node1.data.parent != node2.data.parent) {
          const script_key = `${node1.data.parent}-${node2.data.parent}`;
          if (script_key in script_edges === false) {
            script_edges[script_key] = {
              data: {
                id: script_key,
                source: node1.data.parent,
                target: node2.data.parent,
                field_label: "",
              },
            };
          }
        }
        let field_label = `${field1.name}-${field2.name}`;
        if (link_info) {
          field_label += "\n" + link_info.join(", ");
        }
        edges.push({
          data: {
            id: key1,
            source: pv1,
            target: pv2,
            field_label: field_label,
          },
        });
      }
    }
  }
  return {
    pv_to_node: pv_to_node,
    ioc_to_node: ioc_to_node,
    script_edges: script_edges,
    edges: edges,
    all_nodes: Object.values(ioc_to_node).concat(Object.values(pv_to_node)),
    all_edges: edges.concat(Object.values(script_edges)),
  };
}

function groups_from_relations(relations, include_unknown) {
  let groups = [];
  let saw = {};
  if (!include_unknown) {
    saw["unknown"] = true;
  }
  for (const [ioc1, ioc2s_dict] of Object.entries(relations.script_relations)) {
    if (ioc1 in saw === false) {
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
        saw[ioc] = true;
      }
    }
  }
  return groups;
}

function filter_elements(info, ioc_list, include_records) {
  if (!ioc_list) {
    return info.all_nodes.concat(info.all_edges);
  }
  let nodes = [];
  let edges = [];
  let records = {};
  for (const node_info of info.all_nodes) {
    if (ioc_list.indexOf(node_info.data.id) >= 0) {
      nodes.push(node_info);
    } else if (
      include_records &&
      ioc_list.indexOf(node_info.data.parent) >= 0
    ) {
      nodes.push(node_info);
      records[node_info.data.id] = true;
    }
  }
  for (const edge_info of info.all_edges) {
    const edge_data = edge_info.data;
    if (
      ioc_list.indexOf(edge_data.source) >= 0 &&
      ioc_list.indexOf(edge_data.target) >= 0
    ) {
      edges.push(edge_info);
    } else if (
      include_records &&
      edge_data.source in records &&
      edge_data.target in records
    ) {
      edges.push(edge_info);
    }
  }
  return nodes.concat(edges);
}

function create_plot(info, ioc_list = null, include_records = false) {
  const filtered_elements = filter_elements(info, ioc_list, include_records);
  if (filtered_elements.length == 0) {
    console.debug("No IOCs after selection (or still loading)");
    return null;
  }

  let layout_options;
  if (include_records) {
    layout_options = {
      name: "fcose",
      animate: false,
      nodeDimensionsIncludeLabels: true,
      nodeSeparation: 200,
      quality: "proof",
      randomize: false,
      tile: true,
      uniformNodeDimensions: false,
    };
  } else {
    layout_options = {
      name: "fcose",
      animate: false,
      nodeDimensionsIncludeLabels: true,
      nodeSeparation: 200,
      quality: "proof",
      randomize: false,
      tile: true,
      uniformNodeDimensions: false,
    };
  }
  let cy = cytoscape({
    container: document.getElementById("graph"),
    elements: filtered_elements,
    ready: function () {},
    style: [
      {
        selector: ".pv",
        style: {
          "background-color": "lightgreen",
          label: "data(id)",
          width: "label", // TODO: deprecated
          "text-valign": "center",
          "border-style": "solid",
          "border-color": "gray",
        },
      },
      {
        selector: ".script",
        style: {
          "background-color": "lightgray",
          shape: "rectangle",
          label: "data(id)",
          "text-valign": "bottom",
          "border-style": "dashed",
          "border-color": "black",
        },
      },

      {
        selector: "edge",
        style: {
          label: "data(field_label)",
          width: 1,
          "line-color": "black",
          "target-arrow-color": "#ccc",
          "target-arrow-shape": "triangle",
          "curve-style": "bezier",
          "text-valign": "top",
          "text-margin-y": "-10",
          "text-wrap": "wrap",
        },
      },
    ],

    layout: layout_options,
  });

  return cy;
}

export default {
  name: "PVRelationsView",
  components: {
    Button,
    Column,
    DataTable,
    InputSwitch,
    InputText,
  },
  props: {
    filename: String,
    line: String,
  },
  data() {
    return {
      last_query: null,
      full_relations: false,
      group_filters: null,
      groups: [],
      include_unknown: false,
      metadata: null,
      node_info: null,
      relations: [],
      selected_groups: null,
      show_records: true,
      selected_record: null,
      shown_record: null,
    };
  },
  computed: {
    route_groups() {
      if (!this.$route.query.groups) {
        return [];
      }
      if (typeof this.$route.query.groups == "string") {
        return [this.$route.query.groups];
      }
      return [this.$route.query.groups];
    },
    selected_groups_list() {
      let groups = [];
      for (const group of this.selected_groups) {
        groups.push(group.name);
      }
      return groups;
    },
    selected_ioc_list() {
      if (!this.selected_groups) {
        return [];
      }
      let iocs = [];
      for (const group of this.selected_groups) {
        for (const ioc of group.iocs) {
          iocs.push(ioc);
        }
      }
      return iocs;
    },
    ...mapState({
      pv_relations(state) {
        return state.pv_relations;
      },
    }),
  },
  async created() {
    document.title = `WhatRecord? PV Map`;
    this.init_group_filters();
    this.$watch(
      () => this.$route.params,
      (to_params) => {
        this.from_params(to_params);
      }
    );
    await this.from_params();
  },
  async mounted() {
    if (!Object.keys(this.pv_relations).length) {
      await this.$store.dispatch("get_pv_relations");
    }
    await this.from_params();
  },
  methods: {
    async from_params() {
      const route_query = this.$route.query;
      const query = {
        groups: this.route_groups,
        show_records: route_query.show_records === "true",
        include_unknown: route_query.unknowns === "true",
      };

      if (this.last_query != query && Object.keys(this.pv_relations).length) {
        this.last_query = query;

        this.groups = groups_from_relations(
          this.pv_relations,
          query.include_unknown
        );
        let group_by_name = {};
        for (const group of this.groups) {
          group_by_name[group.name] = group;
        }
        this.selected_groups = [];
        for (const group of query.groups) {
          this.selected_groups.push(group_by_name[group]);
        }

        if (this.full_relations) {
          this.node_info = get_all_nodes(
            this.pv_relations,
            query.include_unknown
          );
        } else {
          this.node_info = get_simple_nodes(
            this.pv_relations,
            query.include_unknown,
            query.show_records
          );
        }

        try {
          this.cy = create_plot(
            this.node_info,
            this.selected_ioc_list,
            query.show_records
          );
        } catch (error) {
          console.error("Failed to update plot", error);
          this.cy = null;
        }
        if (this.cy) {
          this.cy.on("click", "node", this.node_selected);
        }
      }

      const record = route_query.record;
      if (record && this.shown_record != record) {
        this.shown_record = record;
        axios
          .get("/api/pv/" + record + "/graph/svg", {})
          .then((response) => {
            var parser = new DOMParser();
            let svg_doc = parser.parseFromString(
              response.data,
              "image/svg+xml"
            );

            const node_info_div = document.getElementById("node_info");
            node_info_div.replaceChildren(
              svg_doc.getElementsByTagName("svg")[0]
            );
            node_info_div.classList = ["column", "shown"];
          })
          .catch((error) => {
            console.log(error);
          });
      }
    },
    push_route() {
      this.$router.push({
        query: {
          record: this.selected_record,
          show_records: this.show_records,
          unknowns: this.include_unknown,
          groups: this.selected_groups_list,
          global_filter: this.group_filters["global"].value,
        },
      });
    },

    node_selected(event) {
      const node = event.target;
      if (node.hasClass("script")) {
        const ioc_name = node.data().id;
        this.$router.push({
          name: "iocs",
          params: {
            selected_iocs_in: ioc_name,
          },
          query: {
            ioc_filter: ioc_name,
          },
        });
      } else if (node.hasClass("pv")) {
        this.selected_record = node.data().id;
        this.push_route();
      }
    },

    clear_group_filters() {
      this.init_group_filters();
    },

    init_group_filters() {
      this.group_filters = {
        global: { value: this.ioc_filter, matchMode: FilterMatchMode.CONTAINS },
        iocs: { value: null, matchMode: FilterMatchMode.CONTAINS },
      };
    },
  },
};
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
  min-width: 15vw;
  max-width: 17vw;
  max-height: 97vh;
}

#graph {
  height: calc(100vh - 100px);
  min-width: 60vw;
  max-width: 85vw;
}
</style>
