<template>
  <div id="contents">
    <div id="left" class="column">
      <div>
        <h3>Include unknown</h3>
        <InputSwitch v-model="include_unknown" :binary="true" @change="update_plot" />
      </div>
      <div>
        <h3>Show records</h3>
        <InputSwitch v-model="show_records" :binary="true" @change="update_plot" />
      </div>
      <div>
        <h3>Groups</h3>
        <DataTable id="groups" :value="groups" dataKey="name"
            v-model:selection="selected_groups"
            selectionMode="multiple" @rowSelect="new_group_selection"
            :paginator="true" :rows="300" v-model:filters="group_filters"
            filterDisplay="row" :globalFilterFields="['iocs']"
            >
          <template #header>
            <div class="p-d-flex p-jc-between">
              <Button type="button" icon="pi pi-filter-slash" label="Clear" class="p-button-outlined" @click="clear_group_filters()"/>
              <span class="p-input-icon-left">
                <i class="pi pi-search" />
                <InputText v-model="group_filters['global'].value" placeholder="Search" />
              </span>
            </div>
          </template>
          <Column field="iocs" header="IOC Names">
            <template #body="{data}">
              <template v-for="ioc in data.iocs" :key="ioc">
                {{ioc}}<br/>
              </template>
            </template>
          </Column>
        </DataTable>
      </div>
    </div>
    <div id="graph" class="column">
    </div>
  </div>
</template>

<script>
import { mapState } from 'vuex';

import Button from 'primevue/button';
import InputSwitch from 'primevue/inputswitch';
import Column from 'primevue/column';
import DataTable from 'primevue/datatable';
import InputText from 'primevue/inputtext';
import {FilterMatchMode} from 'primevue/api';

import cytoscape from 'cytoscape';
import fcose from 'cytoscape-fcose';

cytoscape.use( fcose );

function get_simple_nodes(relations, include_unknown = false, include_records = false) {
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
        classes: [
          "script",
        ],
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
          }
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
              classes: [
                "pv",
              ],
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
  }
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
      classes: [
        "script",
      ],
    };
    ioc_to_node[script_id] = script_node;
    for (const pv of pvs) {
      const pv_node = {
        data: {
          id: pv,
          parent: script_id,
          weight: 1,
        },
        classes: [
          "pv",
        ],
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
              }
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
          }
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
  }
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
      const name = `${ioc1}-${ioc2s.join(",")}`;
      let group_iocs = [ioc1].concat(ioc2s);
      if (!include_unknown) {
        group_iocs = group_iocs.filter(item => item != "unknown");
      }
      if (group_iocs.length > 1) {
        groups.push(
          {
            "name": name,
            "iocs": group_iocs,
          }
        )
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
    } else if (include_records && ioc_list.indexOf(node_info.data.parent) >= 0) {
      nodes.push(node_info);
      records[node_info.data.id] = true;
    }
  }
  for (const edge_info of info.all_edges) {
    const edge_data = edge_info.data;
    if (ioc_list.indexOf(edge_data.source) >= 0 && ioc_list.indexOf(edge_data.target) >= 0) {
      edges.push(edge_info);
     } else if (include_records && edge_data.source in records && edge_data.target in records) {
      edges.push(edge_info);
    }
  }
  return nodes.concat(edges);
}


function create_plot(info, ioc_list = null, include_records = false) {
  const filtered_elements = filter_elements(info, ioc_list, include_records);
  let layout_options;
  if (include_records) {
    layout_options = {
      name: 'fcose',
      animate: false,
      nodeDimensionsIncludeLabels: true,
      nodeSeparation: 200,
      quality: 'proof',
      randomize: false,
      tile: true,
      uniformNodeDimensions: false,
    }
  } else {
    layout_options = {
      name: 'fcose',
      animate: false,
      nodeDimensionsIncludeLabels: true,
      nodeSeparation: 200,
      quality: 'proof',
      randomize: false,
      tile: true,
      uniformNodeDimensions: false,
    }
  }
  let cy = cytoscape({
    container: document.getElementById('graph'),
    elements: filtered_elements,
    ready: function() {
    },
    style: [
      {
        selector: '.pv',
        style: {
          'background-color': 'lightgreen',
          'label': 'data(id)',
          'width': 'label',   // TODO: deprecated
          'text-valign': 'center',
          'border-style': 'solid',
          'border-color': 'gray',
        }
      },
      {
        selector: '.script',
        style: {
          'background-color': 'lightgray',
          'shape': 'rectangle',
          'label': 'data(id)',
          'text-valign': 'bottom',
          'border-style': 'dashed',
          'border-color': 'black',
        }
      },

      {
        selector: 'edge',
        style: {
          'label': 'data(field_label)',
          'width': 1,
          'line-color': 'black',
          'target-arrow-color': '#ccc',
          'target-arrow-shape': 'triangle',
          'curve-style': 'bezier',
          'text-valign': 'top',
          'text-margin-y': '-10',
          'text-wrap': 'wrap',
        }
      }
    ],

    layout: layout_options,
  });


  return cy;
}

export default {
  name: 'PVRelationsView',
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
      full_relations: false,
      group_filters: null,
      groups: [],
      include_unknown: false,
      metadata: null,
      node_info: null,
      relations: [],
      selected_groups: null,
      show_records: false,
    }
  },
  computed: {
    selected_ioc_list () {
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
      pv_relations (state) {
        return state.pv_relations;
      },
    }),
  },
  created() {
    document.title = `WhatRecord? PV Map`;
    this.init_group_filters();
  },
  async mounted() {
    if (!Object.keys(this.pv_relations).length) {
      await this.$store.dispatch("get_pv_relations");
    }
    this.update_plot();

  },
  methods: {
    update_plot() {
      if (!Object.keys(this.pv_relations).length) {
        return;
      }
      /* console.debug("Update plot", this.include_unknown, this.selected_ioc_list); */
      this.groups = groups_from_relations(this.pv_relations, this.include_unknown);
      if (this.full_relations) {
        this.node_info = get_all_nodes(this.pv_relations, this.include_unknown);
      } else {
        this.node_info = get_simple_nodes(this.pv_relations, this.include_unknown, this.show_records);
      }
      this.cy = create_plot(this.node_info, this.selected_ioc_list, this.show_records);
      this.cy.on("click", "node", this.node_selected);
    },

    node_selected (event) {
      const node = event.target;
      if (node.hasClass("script")) {
        const ioc_name = node.data().id;
        this.$router.push({
          name: "iocs",
          params: {
            "selected_iocs_in": ioc_name,
          },
          query: {
            "ioc_filter": ioc_name,
          },
        });
      } else if (node.hasClass("pv")) {
        const pv_name = node.data().id;
        this.$router.push({
          name: "whatrec",
          params: {
            "record_glob": pv_name,
          },
          query: {
            "selected_records": pv_name,
          },
        });
      }
    },

    new_group_selection(event, push_route=true) {
      this.cy = create_plot(this.node_info, this.selected_ioc_list, this.show_records);
      if (push_route) {
        this.$router.push({
          /* TODO
          params: {
            "selected_iocs_in": this.selected_ioc_list.join("|"),
          }, */
          query: {
            "global_filter": this.group_filters["global"].value,
          }
        });
      }
    },

    clear_group_filters() {
      this.init_group_filters();
    },

    init_group_filters() {
      this.group_filters = {
        'global': {value: this.ioc_filter, matchMode: FilterMatchMode.CONTAINS},
        'iocs': {value: null, matchMode: FilterMatchMode.CONTAINS},
      };
    },

  }
}
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
  min-width: 75vw;
  max-width: 85vw;
}

</style>
