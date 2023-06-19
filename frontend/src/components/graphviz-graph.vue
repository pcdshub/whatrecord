<template>
  <a id="save-svg" target="_blank">Save</a>
  <div id="d3-rendered-graph" />
</template>

<script lang="ts">
import { graphviz } from "d3-graphviz";

export default {
  name: "GraphvizGraph",
  props: {
    width: {
      type: Number,
      required: true,
    },
    height: {
      type: Number,
      required: true,
    },
    // Fit graph
    fit_graph: Boolean,
    // Graphviz .dot source code
    dot_source: String,
    // Filename to download the graph as
    save_filename: String,
  },
  async mounted() {
    try {
      await this.update_graph();
    } catch (err) {
      console.error("Graphviz graph failed on mount:", err);
    }
  },
  async updated() {
    try {
      await this.update_graph();
    } catch (err) {
      console.error("Graphviz graph failed on update:", err);
    }
  },
  methods: {
    async update_graph() {
      const save_element = document.getElementById(
        "save-svg",
      ) as HTMLAnchorElement | null;
      if (save_element != null) {
        save_element.hidden = (this.dot_source ?? "") === "";
      }
      const graph = graphviz("#d3-rendered-graph");
      graph.renderDot(this.dot_source ?? "");
      if (this.fit_graph) {
        graph.fit(this.fit_graph);
      } else {
        graph.width(Math.max(this.width, 300));
        graph.height(Math.max(this.height, 300));
        graph.fit(true);
      }
      graph.render(this.finished_d3_graph_render);
    },
    finished_d3_graph_render() {
      console.debug("Finished render; creating link...");
      const graph_elem = document.getElementById(
        "d3-rendered-graph",
      ) as HTMLDivElement | null;
      if (!graph_elem) {
        return;
      }
      // For removing &nbsp; and such:
      const dummy: HTMLDivElement = document.createElement("div");

      function decode_html(match: string, ..._args: any): string {
        dummy.innerHTML = match;
        return dummy.textContent ?? "";
      }

      let svg_data = graph_elem.innerHTML.replace(
        /(&(?!(amp|gt|lt|quot|apos))[^;]+;)/g,
        decode_html,
      );
      const preface = '<?xml version="1.0" standalone="no"?>\r\n';
      const blob = new Blob([preface, svg_data], {
        type: "image/svg+xml;charset=utf-8",
      });
      let url = URL.createObjectURL(blob);
      const save_element = document.getElementById(
        "save-svg",
      ) as HTMLAnchorElement | null;
      if (save_element !== null) {
        save_element.href = url;
        save_element.download = `${this.save_filename}.svg`;
      }
    },
  },
};
</script>

<style scoped>
/*
#d3-rendered-graph {
}

#save-svg {
}
*/
</style>
