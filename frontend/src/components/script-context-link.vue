<template>
  <div class="context">
  <script-context-one-link
    v-for:="ctx in context"
    :name="ctx[0]"
    :line="ctx[1]"
    :short=short
  ></script-context-one-link>
  </div>
</template>

<script>
import ScriptContextOneLink from './script-context-one-link.vue'

export default {
  name: 'ScriptContextLink',
  props: {
    context: Array,
    short: Boolean
  },
  components: {
    ScriptContextOneLink
  }
}
</script>

<style scoped>
</style>
