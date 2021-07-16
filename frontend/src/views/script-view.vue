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
import { mapState } from 'vuex';

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
    }
  },
  computed: {
    metadata () {
      return this.file_info ? this.file_info.ioc : {};
    },
    lines () {
      return this.file_info ? this.file_info.script.lines : [];
    },
    ...mapState({
      file_info (state) {
        return state.file_info[this.filename] || null;
      },
    })
  },
  async mounted() {
    this.$store.dispatch(
      "get_file_info",
      { filename: this.filename }
    );
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
