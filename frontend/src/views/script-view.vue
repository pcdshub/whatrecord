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
          <script-line v-for="(line, idx) in lines"
             :line="line"
             :all_commands="commands"
             :key="idx"
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
    commands () {
      return this.metadata ? this.metadata.commands : {};
    },
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
