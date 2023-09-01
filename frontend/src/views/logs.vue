<template>
  <div id="script">
    <pre v-for="(line, idx) in log_lines" :key="idx">{{ line }}</pre>
  </div>
</template>

<script lang="ts">
import { use_configured_store } from "../stores";

export default {
  name: "ServerLogView",
  components: {},
  props: {},
  data() {
    return {
      log_lines: [] as string[],
      metadata: null,
    };
  },
  setup() {
    const store = use_configured_store();
    return { store };
  },
  async mounted() {
    document.title = "whatrecord? Server logs";
    this.log_lines = await this.store.get_server_logs();
  },
  updated() {
    const script = document.getElementById("script");
    if (script != null) {
      script.scrollIntoView({ block: "end" });
    }
  },
};
</script>

<style scoped></style>
