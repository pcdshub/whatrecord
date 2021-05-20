<template>
  <div class="p-d-flex">
    <div class="p-md-2">
      <Searchbar @gotRecordInfo="this.record_info = $event" />
    </div>
    <div class="p-md-8" id="record_info">
      <div v-for="match in record_info" :key="match.pv_name">
        <h3> {{ match.pv_name }} </h3>
        <Recordinfo
          v-for="(info, idx) in match.info"
          :key="idx"
          :record_info="info"
          :appliance_viewer_url="appliance_viewer_url"
        />
      </div>
    </div>
  </div>
</template>

<script>
import Recordinfo from './components/recordinfo.vue'
import Searchbar from './components/searchbar.vue'

export default {
  name: 'WhatRec',
  components: {
    Recordinfo,
    Searchbar,
  },
  data() {
    return {
      pv_glob: '*MMS:*',
      max_pvs: 30,
      selected_pvs: [],
      add_graph: true,
      pv_list: [],
      record_info: {},
      appliance_viewer_url: 'https://pswww.slac.stanford.edu/archiveviewer/retrieval/ui/viewer/archViewer.html?pv=',
    }
  },
  mounted() {
    // Split({})
  },
  methods: {
  }
}
</script>

<style>
#app {
  font-family: Avenir, Helvetica, Arial, sans-serif;
  -webkit-font-smoothing: antialiased;
  -moz-osx-font-smoothing: grayscale;
  text-align: center;
  color: #2c3e50;
  margin-top: 60px;
}

#record_info {
  text-align: left;
}

.code {
    background: whitesmoke;
    border: 1px solid lightgray;
    border-left: 3px solid lightcoral;
    color: black;
    page-break-inside: avoid;
    font-family: monospace;
    font-size: 15px;
    line-height: 1.0;
    margin-bottom: 1.6em;
    max-width: 100%;
    overflow: auto;
    padding: 15px;
    display: block;
    word-wrap: break-word;
}

table {
    font-family: monospace;
}

html, body, .top-grid {
  height: 100%;
  padding: 1px;
}

.top-grid {
  display: grid;
  grid-template-columns: 1fr 60% 1fr;
  grid-template-rows: 1fr;
}

.svg-graph {
  max-width: 70%;
}

.error-block {
  background: lightred;
  border: 1px solid lightgray;
  border-left: 3px solid lightcoral;
  color: black;
  page-break-inside: avoid;
  font-family: monospace;
  font-size: 15px;
  line-height: 1.0;
  margin-bottom: 1.6em;
  max-width: 100%;
  overflow: auto;
  padding: 15px;
  display: block;
  word-wrap: break-word;
}

.result-block {
  background: #eeeeee;
  border: 1px solid lightgray;
  border-left: 3px solid lightgray;
  color: black;
  page-break-inside: avoid;
  font-family: monospace;
  font-size: 15px;
  line-height: 1.0;
  margin-bottom: 1.6em;
  max-width: 100%;
  overflow: auto;
  padding: 15px;
  display: block;
  word-wrap: break-word;
}

summary.title {
  font-weight: bold;
  border: 1px black solid;
}

summary.script-line {
}

.script-line {
  color: black;
}

.script-error-line {
  color: red;
}


details.title {
  overflow: hidden;
  margin-top: 1em;
  margin-bottom: 1em;
}

.context {
  margin-left: 1px;
}
</style>
