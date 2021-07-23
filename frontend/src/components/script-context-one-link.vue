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
    short: Boolean,
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
      return (this.short ? this.short_name : this.name);
    },
    short_name() {
      return this.name.replace(/^.*[\\/]/, '');
    },
    link() {
      return { name: 'file', params: { filename: this.name, line: this.line }};
    }
  }
}
</script>

<style scoped>
</style>
