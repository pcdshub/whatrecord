<template>
  <div id="contents">
    <div id="left" class="column">
      <Searchbar :pattern="pattern" :record="record" :use_regex="use_regex" />
    </div>
    <div id="right" class="column">
      <div v-for="match in record_info" :key="match.pv_name">
        <Recordinfo
          v-for="(whatrec, idx) in match.info"
          :key="idx"
          :whatrec="whatrec"
        />
      </div>
    </div>
  </div>
</template>

<script lang="ts">
import { use_configured_store } from "../stores";

import Recordinfo from "../components/recordinfo.vue";
import Searchbar from "../components/searchbar.vue";

export default {
  name: "WhatRec",
  components: {
    Recordinfo,
    Searchbar,
  },
  props: {
    pattern: {
      type: String,
      required: true,
    },
    use_regex: {
      type: Boolean,
      default: false,
    },
    record: {
      type: Array<string>,
      required: true,
    },
  },
  setup() {
    const store = use_configured_store();
    return { store };
  },
  computed: {
    record_info() {
      let record_info = [];
      for (const rec of this.record) {
        if (rec in this.store.record_info) {
          record_info.push(this.store.record_info[rec]);
        }
      }
      return record_info;
    },
  },
  data() {
    return {};
  },
  created() {
    console.debug(
      `whatrecord Mounted: glob=${this.pattern} PVs=${this.record}`,
    );
  },
};
</script>

<style scoped>
#contents {
  flex-direction: row;
  justify-content: flex-start;
  display: flex;
  overflow: scroll;
  height: 93vh;
}

.column {
  display: flex;
  flex-direction: column;
  flex-shrink: 0;
  justify-content: flex-start;
  overflow: scroll;
}

#left {
  min-width: 15%;
  max-width: 20%;
  border-right: 1px dotted;
}

#right {
  margin: 1em;
  min-width: 75%;
  max-width: 100%;
}
</style>
