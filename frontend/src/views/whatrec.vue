<template>
  <div id="contents">
    <div id="left">
      <Searchbar :route_record_glob="search_record_glob" :route_selected_records="search_selected_records" />
    </div>
    <div id="right" class="column">
      <div v-for="match in record_info" :key="match.pv_name">
        <Recordinfo
          v-for="(whatrec, idx) in match.info"
          :key="idx"
          :whatrec="whatrec"
          :appliance_viewer_url="appliance_viewer_url"
        />
      </div>
    </div>
  </div>
</template>

<script>
import Recordinfo from '../components/recordinfo.vue'
import Searchbar from '../components/searchbar.vue'

export default {
  name: 'WhatRec',
  components: {
    Recordinfo,
    Searchbar,
  },
  props: ["record_glob", "selected_records"],
  computed: {
    record_info() {
      return this.$store.getters.selected_record_info;
    }
  },
  data() {
    return {
      appliance_viewer_url: 'https://pswww.slac.stanford.edu/archiveviewer/retrieval/ui/viewer/archViewer.html?pv=',
      search_record_glob: "",
      search_selected_records: [],
    }
  },
  created() {
    console.debug(`Whatrec Mounted: glob=${this.record_glob} PVs=${this.selected_records}`);
    this.search_selected_records = (this.selected_records || "").split("|");
    this.search_record_glob = this.record_glob || "*";

    this.$store.dispatch("set_record_glob", {"record_glob": this.search_record_glob, max_pvs: 200});
    this.$store.dispatch("set_selected_records", {"records": this.search_selected_records});
  },
  async beforeRouteUpdate(to, from) {
    // TODO: linter unused vars?
    console.debug("Route from", from, "to", to);

    const selected_records = (to.params.selected_records || "").split("|");
    this.$store.dispatch("set_record_glob", {"record_glob": to.params.record_glob, max_pvs: 200});
    this.$store.dispatch("set_selected_records", {"records": selected_records});

    this.table_selection = [];
    for (const rec of selected_records) {
      this.table_selection.push({"pv": rec});
    }
    this.search_record_glob = to.record_glob || "*";
    this.search_selected_records = selected_records;
  },

}
</script>

<style scoped>
#contents {
  flex-direction: row;
  justify-content: flex-start;
  display: flex;
  overflow: scroll;
  height: 97vh;
}

.column {
  display: flex;
  flex-direction: column;
  flex-shrink: 0;
  justify-content: flex-start;
  overflow: scroll;
}

#left {
  min-width: 15vw;
  max-width: 20vw;
}

#right {
  margin: 1em;
  min-width: 50%;
}
</style>
