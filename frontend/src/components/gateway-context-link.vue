<template>
  <a :href="'/database?file=' + filename + '#' + lineno" target="_blank">
    {{ filename.replace(/^.*[\\\/]/, '') }}:{{ lineno }}
  </a>
</template>

<script>
export default {
  name: 'GatewayContextLink',
  props: {
    filename: String,
    lineno: Number
  }
}
</script>

<style scoped>
</style>
