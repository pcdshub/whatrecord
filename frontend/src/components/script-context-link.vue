<template>
  <div class="context">
    <template v-for="[name, line] in context" :key="name + line">
      &gt;
        <script-context-one-link
          :name="name"
          :line="line"
          :short="short"
        />
        <br />
    </template>
  </div>
</template>

<script>
import ScriptContextOneLink from './script-context-one-link.vue'

export default {
  name: 'ScriptContextLink',
  props: {
    context: Array,
    short: Number
  },
  components: {
    ScriptContextOneLink
  }
}
</script>

<style scoped>
</style>
