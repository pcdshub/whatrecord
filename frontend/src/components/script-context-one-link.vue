<template>
  &gt;
  <router-link :to="link">
    {{ display_name }}:{{ line }}<br/>
  </router-link>
</template>

<script>
export default {
  name: 'ScriptContextOneLink',
  props: {
    name: String,
    line: Number,
    short: Boolean,
  },
  computed: {
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
