<template>
  <div id="script">
    <pre v-for="(line, idx) in log_lines" :key="idx">{{ line }}</pre>
  </div>
</template>

<script lang="ts">
import axios from "axios";

export default {
  name: "ServerLogView",
  components: {},
  props: {
    filename: String,
    line: String,
  },
  data() {
    return {
      log_lines: [],
      metadata: null,
    };
  },
  async mounted() {
    try {
      const response = await axios.get("/api/logs/get", { params: {} });
      this.log_lines = response.data;
      document.title = "whatrecord? Server logs";
    } catch (error) {
      console.error(error);
    }
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
