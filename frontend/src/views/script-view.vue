<template>
  <button @click="expand_all">Expand all</button>
  <div>
    <div>
      <h2>{{ filename }}<template v-if="line > 0">:{{ line }}</template></h2>
      <template v-if="metadata">
        <details>
          <summary>{{ metadata.name }}</summary>
          <dictionary-table
            :dict="metadata"
            cls="metadata"
            :skip_keys="['commands', 'variables']">
          </dictionary-table>
        </details>
      </template>
      <table>
        <tbody>
          <script-line v-for="line in lines"
             :argv="line.argv"
             :context="line.context"
             :error="line.error"
             :line="line.line"
             :outputs="line.outputs"
             :redirects="line.redirects"
             :result="line.result"
             :command_info="(line.argv != null && line.argv.length > 0) ? metadata.commands[line.argv[0]] : null"
             :key="line.context.map(ctx => ctx[0] + ':' + ctx[1]).join(',')"
             />
        </tbody>
      </table>
    </div>
  </div>
</template>

<script>
const axios = require('axios').default;

import DictionaryTable from '../components/dictionary-table.vue';
import ScriptLine from '../components/script-line.vue';

export default {
  name: 'ScriptView',
  components: {
    DictionaryTable,
    ScriptLine,
  },
  props: {
    filename: String,
    line: String,
  },
  data() {
    return {
      lines: [],
      metadata: null,
    }
  },
  async mounted() {
    try {
      const response = await axios.get("/api/file/info", {params: { file: this.filename } })
      this.metadata = response.data.ioc;
      this.lines = response.data.script.lines;
      document.title = "WhatRec? " + this.filename;
    } catch (error) {
      console.error(error)
    }
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
      document.body.querySelectorAll('details').forEach(
        (details) =>
        (details.hasAttribute('open')) ? details.removeAttribute('open') : details.setAttribute('open',true)
      );
    }
  }
}
</script>

<style scoped>
table {
  width: 100%;
}
</style>
