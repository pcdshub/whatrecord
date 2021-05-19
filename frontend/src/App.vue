<template>
  <div id="whatrec" class="top-grid">
    <div>
      <form @submit.prevent="search">
        Search: <input v-model.trim.lazy="pv_glob" placeholder="" /><br/>
        Max: <input v-model.number.lazy="max_pvs" placeholder="200" type="number" /><br/>
        <!-- <p>Query: {{ pv_glob }} (max {{ max_pvs }})</p> -->
        <button @click="search()">Search</button>
        <button @click="whatrec()">whatrecord?</button>
        <br/>
        <template v-for="(pvname, idx) in pv_list" :key=idx>
          <input :id="pvname" :value="pvname" name="pvname" type="checkbox" v-model="selected_pvs" />
          <label :for="pvname"><span classname="pvname">{{pvname}}</span></label>
          <br/>
        </template>
      </form>
    </div>
    <div>
      <div v-for="match in pv_info" :key=match.pv_name >
        <h3> {{ match.pv_name }} </h3>
        <recordinfo
          v-for="(info, idx) in match.info"
          :key=idx
          :info="info"
          :appliance_viewer_url="appliance_viewer_url" />
      </div>
    </div>
  </div>
</template>

<script>
const axios = require('axios').default;

// import AsynPort from './components/asyn-port.vue'
// import DictionaryTable from './components/dictionary-table.vue'
// import EpicsFormatRecord from './components/epics-format-record.vue'
// import GatewayContextLink from './components/gateway-context-link.vue'
// import GatewayMatches from './components/gateway-matches.vue'
// import RecordFieldTable from './components/record-field-table.vue'
import Recordinfo from './components/recordinfo.vue'
// import ScriptContextLink from './components/script-context-link.vue'
// import ScriptContextOneLink from './components/script-context-one-link.vue'

export default {
  name: 'WhatRec',
  components: {
    // AsynPort,
    // DictionaryTable,
    // EpicsFormatRecord,
    // GatewayContextLink,
    // GatewayMatches,
    // RecordFieldTable,
    Recordinfo,
    // ScriptContextLink,
    // ScriptContextOneLink,
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
