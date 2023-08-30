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

<script lang="ts">
import { use_configured_store } from "../stores";

import DictionaryTable from "../components/dictionary-table.vue";
import ScriptLine from "../components/script-line.vue";
import { IocMetadata, IocshCommand, IocshResult, FileInfo } from "../types";
import { FullLoadContext } from "../types";

function remove_xml(filename: string, lines: IocshResult[]): IocshResult[] {
  // Strip the <xml> header
  const raw_xml = lines
    .slice(1)
    .map((line) => line.line)
    .join("\n");

  let parser = new DOMParser();
  let xml = parser.parseFromString(raw_xml, "text/xml");

  const sections = [
    xml.querySelectorAll("Declaration")?.item(0),
    xml.querySelectorAll("Implementation")?.item(0),
  ];
  const code = sections.map((section) => section?.textContent ?? "").join("\n");

  return code.split("\n").map(
    (line, lineno) =>
      ({
        context: [[filename, lineno + 1]] as FullLoadContext,
        line: line,
        outputs: [],
        argv: [],
        error: "",
        redirects: [],
        result: null,
      }) as IocshResult,
  );
}

export default {
  name: "ScriptView",
  setup() {
    const store = use_configured_store();
    return { store };
  },
  components: {
    DictionaryTable,
    ScriptLine,
  },
  props: {
    filename: {
      type: String,
      required: true,
    },
    line: {
      type: Number,
      required: true,
    },
  },
  data() {
    return {
      last_filename: "",
    };
  },
  computed: {
    commands(): Record<string, IocshCommand> {
      return this.metadata?.commands ?? {};
    },
    metadata(): IocMetadata | null {
      return this.file_info?.ioc ?? null;
    },
    is_twincat_file() {
      const extension = this.filename.split(".").pop() || "";
      return (
        ["tcpou", "tcgvl", "tcdut", "tcio"].indexOf(extension.toLowerCase()) >=
        0
      );
    },
    lines(): IocshResult[] {
      if (this.file_info === null) {
        return [];
      }
      if (this.is_twincat_file) {
        return remove_xml(this.filename, this.file_info.script.lines ?? []);
      }
      return this.file_info.script.lines ?? [];
    },
    file_info(): FileInfo | null {
      return this.store.file_info[this.filename] ?? null;
    },
  },

  async mounted() {
    await this.load_and_scroll();
  },

  async updated() {
    await this.load_and_scroll();
  },

  watch: {
    async $route() {
      await this.load_and_scroll();
    },
  },

  methods: {
    async load_and_scroll() {
      await this.update_store();
      this.scroll_into_view();
    },
    scroll_into_view() {
      const lineno = this.line;
      const obj = document.getElementById(lineno.toString());
      if (obj != null) {
        obj.scrollIntoView();
      }
    },
    async update_store() {
      if (this.filename == this.last_filename) {
        return;
      }
      this.last_filename = this.filename;
      document.title = "whatrecord? Script " + this.filename;
      await this.store.get_file_info({ filename: this.filename });
    },
    expand_all() {
      document.body
        .querySelectorAll("details")
        .forEach((details) =>
          details.hasAttribute("open")
            ? details.removeAttribute("open")
            : details.setAttribute("open", "true"),
        );
    },
    get_line_id(line: IocshResult): string {
      return line.context?.map((ctx) => ctx[1]).join(":") ?? "";
    },
  },
};
</script>

<style scoped>
table {
  width: 100%;
}
</style>
