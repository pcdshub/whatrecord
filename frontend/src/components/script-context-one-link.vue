<template>
  &gt;
  <a v-if="name.indexOf('.cmd') >= 0"
      :href="'/script?script=' + name + '#' + name + ':' + line"
      target="_blank">
    <template v-if="short">
        {{ name.replace(/^.*[\\\/]/, '') }}:{{ line }}<br/>
    </template>
    <template v-else>
        {{ name }}:{{ line }}<br/>
    </template>
  </a>
  <a v-else
        :href="'/database?file=' + name + '#' + line"
        target="_blank">
    <template v-if="short">
        {{ name.replace(/^.*[\\\/]/, '') }}:{{ line }}<br/>
    </template>
    <template v-else>
        {{ name }}:{{ line }}<br/>
    </template>
  </a>
</template>

<script>
export default {
  name: 'ScriptContextOneLink',
  props: {
    short: Boolean,
    name: String,
    line: Number
  }
}
</script>

<style scoped>
</style>
