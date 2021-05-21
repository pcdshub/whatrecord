<template>
  <a v-bind:href="'/database?file=' + filename + '#' + line" target="_blank">Line {{line}}</a>
</template>

<script>
export default {
  name: 'DbContextLink',
  props: ["filename", "line"],
}
</script>

<style scoped>
</style>
