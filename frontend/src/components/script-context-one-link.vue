<template>
  <router-link :to="link">
    {{ displayed_link_text }}
  </router-link>
</template>

<script lang="ts">
export default {
  name: "ScriptContextOneLink",
  props: {
    name: {
      type: String,
      required: true,
    },
    line: {
      type: Number,
      required: true,
    },
    short: {
      type: Number,
      required: false,
      default: 0,
    },
    link_text: {
      type: String,
      required: false,
      default: "",
    },
  },
  computed: {
    displayed_link_text() {
      if (this.link_text) {
        return this.link_text;
      }
      if (this.line > 0) {
        return `${this.display_name}:${this.line}`;
      } else {
        return this.display_name;
      }
    },
    display_name() {
      return this.short > 0 ? this.short_name : this.name;
    },
    short_name() {
      let parts = this.name.split("/");
      return parts.slice(-this.short).join("/");
    },
    link() {
      return { name: "file", query: { filename: this.name, line: this.line } };
    },
  },
};
</script>

<style scoped></style>
