<template>
  <button @click="expand_all">Expand all</button>
  <div>
    <div>
      <h2>{{ filename }}:{{ line }}</h2>
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
             :key="line.context.map(ctx => ctx[0] + ':' + ctx[1]).join(',')"
             />
        </tbody>
      </table>
    </div>
  </div>
</template>

<script>
const axios = require('axios').default;

import ScriptLine from '../components/script-line.vue';

export default {
  name: 'ScriptView',
  components: {
    ScriptLine,
  },
  props: {
    filename: String,
    line: String,
  },
  data() {
    return {
      lines: [],
    }
  },
  mounted() {
    axios.get(
      "/api/file/info",
      {params:
        {
          file: this.filename,
        }
      }
    )
      .then(response => {
        this.lines = response.data.lines;
        document.title = "WhatRec? " + this.filename;
      })
      .catch(error => {
        console.log(error)
      });
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
</style>
