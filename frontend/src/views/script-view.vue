<template>
  <button @click="expand_all">Expand all</button>
  <div>
    <div>
      <h2>{{ $route.params.file }}:{{ $route.params.line }}</h2>
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
  props: [],
  data() {
    return {
      path: "",
      lines: [],
    }
  },
  mounted() {
    const filename = this.$route.params.file;

    axios.get(
      "/api/file/info",
      {params:
        {
          file: filename,
        }
      }
    )
      .then(response => {
        this.path = response.data.path;
        this.lines = response.data.lines;
        document.title = "WhatRec? " + this.path;
      })
      .catch(error => {
        console.log(error)
      });
  },
  updated() {
    const lineno = this.$route.params.line;
    const obj = document.getElementById(lineno);
    if (obj != null) {
      obj.scrollIntoView();
    }
    // var hash = window.location.hash.substr(1);
    // if (hash != "") {
    //   var obj = document.getElementById(hash);
    //   if (obj != null) {
    //     obj.scrollIntoView();
    //   }
    // }
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
