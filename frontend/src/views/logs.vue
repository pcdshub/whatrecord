<template>
  <pre v-for="(line, idx) in log_lines" :key="idx">{{ line }}</pre>
</template>

<script>
const axios = require('axios').default;

export default {
  name: 'ServerLogView',
  components: {
  },
  props: {
    filename: String,
    line: String,
  },
  data() {
    return {
      log_lines: [],
      metadata: null,
    }
  },
  async mounted() {
    try {
      const response = await axios.get("/api/logs/get", {params: {} })
      this.log_lines = response.data;
      document.title = "WhatRec server logs";
    } catch (error) {
      console.error(error)
    }
  },
}
</script>

<style scoped>
</style>
