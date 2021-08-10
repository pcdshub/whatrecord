<template>
  <router-link :to="link">
    {{ displayed_link_text }}
  </router-link>
</template>

<script>
export default {
  name: 'ScriptContextOneLink',
  props: {
    name: String,
    line: Number,
    short: Number,
    link_text: String,
  },
  computed: {
    displayed_link_text() {
      if (this.link_text) {
        return this.link_text;
      }
      return `${this.display_name }:${this.line}`;
    },
    display_name() {
      return (this.short > 0 ? this.short_name : this.name);
    },
    short_name() {
      let parts = this.name.split("/");
      return parts.slice(-this.short).join("/");
    },
    link() {
      return { name: 'file', params: { filename: this.name, line: this.line }};
    }
  }
}
</script>

<style scoped>
</style>
