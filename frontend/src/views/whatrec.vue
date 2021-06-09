<template>
  <div class="p-grid">
    <div class="p-col-3">
      <Searchbar :pv_glob_default="pv_glob" />
    </div>
    <div class="p-col-7" id="record_info">
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
import { mapState } from 'vuex'

import Recordinfo from '../components/recordinfo.vue'
import Searchbar from '../components/searchbar.vue'

export default {
  name: 'WhatRec',
  components: {
    Recordinfo,
    Searchbar,
  },
  props: ["pv_glob"],
  computed: {
    record_info() {
      return this.$store.getters.selected_record_info;
    },

    ...mapState({
      selected_records: state => state.selected_records,
    })
  },
  data() {
    return {
      add_graph: true,
      appliance_viewer_url: 'https://pswww.slac.stanford.edu/archiveviewer/retrieval/ui/viewer/archViewer.html?pv=',
    }
  },
  mounted() {
    console.log(`Mounted: glob=${this.pv_glob} PVs=${this.pv_from_link}`);
  },
}
</script>

<style>
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

.svg-graph {
  max-width: 70%;
}

.context {
  margin-left: 1px;
}
</style>
