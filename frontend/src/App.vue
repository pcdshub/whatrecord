<template>
  <div id="whatrec" class="top-grid">
    <Searchbar />
    <div align=left>
      <div v-for="match in pv_info" :key=match.pv_name >
        <h3> {{ match.pv_name }} </h3>
        <recordinfo
          v-for="(info, idx) in match.info"
          :key="idx"
          :info="info"
          :appliance_viewer_url="appliance_viewer_url" />
      </div>
    </div>
  </div>
</template>

<script>
const axios = require('axios').default;

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
      add_graph: true,
      pv_list: [],
      pv_info: {},
      selected_pvs: [],
      appliance_viewer_url: 'https://pswww.slac.stanford.edu/archiveviewer/retrieval/ui/viewer/archViewer.html?pv=',
    }
  },
  mounted() {
    // Split({})
  },
  methods: {
    whatrec() {
      axios.get(
        "/api/pv/" + this.selected_pvs.join("|") + "/info",
        {})
        .then(response => {
          console.log(response.data);
          this.pv_info = response.data;
        })
        .catch(error => {
          console.log(error)
        });
    },
    search() {
      document.title = "WhatRec? " + this.pv_glob;
      axios.get(
        "/api/pv/" + this.pv_glob + "/matches",
        {params:
          {
            max: this.max_pvs
          }
        })
        .then(response => {
          console.log(response.data);
          var matching_pvs = response.data["matching_pvs"];
          this.selected_pvs = this.selected_pvs.filter(
            function(v) {return matching_pvs.indexOf(v) >= 0; }
          );
          if (matching_pvs.length > 0 && this.selected_pvs.length == 0) {
            this.selected_pvs = [matching_pvs[0]];
            this.whatrec();
          }
          this.pv_list = matching_pvs;
        })
        .catch(error => {
          console.log(error)
        });
      }
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
</style>
