<template>
  <button @click="expand_all">Expand all</button>
  <div>
    <div>
      <h2>
        {{ filename }}<template v-if="line > 0">:{{ line }}</template>
      </h2>
      <template v-if="metadata">
        <details>
          <summary>{{ metadata.name }}</summary>
          <dictionary-table
            :dict="metadata"
            cls="metadata"
            :skip_keys="['commands', 'variables']"
          >
          </dictionary-table>
        </details>
      </template>
      <table>
        <tbody>
          <script-line
            v-for="line in lines"
            :line="line"
            :all_commands="commands"
            :key="get_line_id(line)"
          />
        </tbody>
      </table>
    </div>
  </div>
</template>

<script>
import { mapState } from "vuex";

import DictionaryTable from "../components/dictionary-table.vue";
import ScriptLine from "../components/script-line.vue";

function remove_xml(filename, lines) {
  // Strip the <xml> header
  const raw_xml = lines.slice(1).map(line => line.line).join("\n");

  let parser = new DOMParser();
  let xml = parser.parseFromString(raw_xml, "text/xml");

  const sections = [
    xml.querySelectorAll("Declaration")?.item(0),
    xml.querySelectorAll("Implementation")?.item(0)
  ];
  const code = sections.map(section => section?.textContent ?? "").join("\n")

  return code.split("\n").map(
      (line, lineno) => (
        {
          line: line,
          context: [[filename, lineno + 1]],
        }
      )
  )
}

export default {
  name: "ScriptView",
  components: {
    DictionaryTable,
    ScriptLine,
  },
  props: {
    filename: String,
    line: String,
  },
  data() {
    return {};
  },
  computed: {
    commands() {
      return this.metadata?.commands ?? {};
    },
    metadata() {
      return this.file_info?.ioc ?? {};
    },
    is_twincat_file() {
      const extension = this.filename.split(".").pop() || "";
      return ["tcpou", "tcgvl", "tcdut"].indexOf(extension.toLowerCase()) >= 0;
    },
    lines() {
      if (this.is_twincat_file) {
          return remove_xml(this.filename, this.file_info?.script.lines ?? []);
      }
      return this.file_info?.script.lines ?? [];
    },
    ...mapState({
      file_info(state) {
        return state.file_info[this.filename] || null;
      },
    }),
  },
  async mounted() {
    this.$store.dispatch("get_file_info", { filename: this.filename });
    document.title = "WhatRecord? Script " + this.filename;
  },
  updated() {
    const lineno = this.line;
    const obj = document.getElementById(lineno);
    if (obj != null) {
      obj.scrollIntoView();
    }
  },
  methods: {
    expand_all() {
      document.body
        .querySelectorAll("details")
        .forEach((details) =>
          details.hasAttribute("open")
            ? details.removeAttribute("open")
            : details.setAttribute("open", true)
        );
    },
    get_line_id(line) {
        return line?.context?.map((ctx) => ctx[1]).join(":") ?? [];
    },
  },
};
</script>

<style scoped>
table {
  width: 100%;
}
</style>
