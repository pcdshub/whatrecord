<template>
  <div id="graph" />
</template>

<script>
const axios = require('axios').default;
import cytoscape from 'cytoscape';
import fcose from 'cytoscape-fcose';

cytoscape.use( fcose );


export default {
  name: 'PVRelationsView',
  components: {
  },
  props: {
    filename: String,
    line: String,
  },
  data() {
    return {
      relations: [],
      metadata: null,
    }
  },
  async mounted() {
    const full = false;
    try {
      const response = await axios.get("/api/pv/*/relations", { params: { full: full } })
      this.relations = response.data;
    } catch (error) {
      console.error(error)
      return;
    }

    let nodes = [];
    let pv_to_node = {};
    let ioc_to_node = {};
    let script_edges = {};
    let edges = [];
    let graphed_fields = [];

    const include_unknown = false;

    if (!full) {
      for (const [ioc1, ioc2s] of Object.entries(this.relations.script_relations)) {
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
              "hide",
            ],
          };
          ioc_to_node[ioc1] = script_node;
          nodes.push(script_node);
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
              nodes.push(pv_node);
              pv_to_node[pv] = pv_node;
            }
          }
        }
      }

    } else {
      // Full relationship of IOC to PVs and per-record fields
      for (const [script_id, pvs] of Object.entries(this.relations.ioc_to_pvs)) {
        let script_node = {
          data: {
            id: script_id,
            weight: 2,
          },
          classes: [
            "script",
            "hide",
          ],
        };
        nodes.push(script_node);
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
          nodes.push(pv_node);
        }
      }

      for (const [pv1, pv2s] of Object.entries(this.relations.pv_relations)) {
        const node1 = pv_to_node[pv1];
        // Full field info with context and all; may be too huge to serialize
        for (const [pv2, fields] of Object.entries(pv2s)) {
          if (pv1 === pv2) {
            continue;
          }
          const node2 = pv_to_node[pv2];
          for (const field_info of fields) {
            const field1 = field_info.fields[0]
            const field2 = field_info.fields[1]
            const link_info = field_info.info
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
    }

    function toggle_node_visibility(node) {
      const descendants = node.descendants();
      for (const child of descendants) {
        if (child.style("display") == "none") {
          child.style("display", "element");
        } else {
          child.style("display", "none");
        }
      }
    }

    let cy = cytoscape({
      container: document.getElementById('graph'),
      elements: nodes.concat(edges).concat(Object.values(script_edges)),
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
            'shape': 'rectangle',
            'border-style': 'solid',
            'border-color': 'gray',
          }
        },
        {
          selector: '.script',
          style: {
            'background-color': 'lightgray',
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

      layout: {
        name: 'fcose',
        quality: 'proof',
        animate: false,
        nodeDimensionsIncludeLabels: true,
        uniformNodeDimensions: false,
        nodeSeparation: 75,
        tile: true,
        randomize: false,
      },
    });


    cy.on("click", "node", function (event) {
      toggle_node_visibility(event.target);
    });

    cy.nodes().forEach(
      node => toggle_node_visibility(node)
    );
    this.cy = cy;

  },
}
</script>

<style>
.node {
  stroke: #fff;
  stroke-width: 1.5px;
  cursor: move;
}

.group {
  stroke: #fff;
  stroke-width: 1.5px;
  cursor: move;
  opacity: 0.7;
}

.link {
  fill: none;
  stroke: #000;
  stroke-width: 3px;
  opacity: 0.7;
  marker-end: url(#end-arrow);
}

.label {
    fill: white;
    font-family: Courier;
    font-size: 12px;
    text-anchor: middle;
    cursor: move;
}

#graph {
    height: calc(100vh - 100px);
}
</style>
