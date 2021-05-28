<template>
  <div class="context">
    <script-context-one-link
      v-for:="ctx in context"
      :name="ctx.file"
      :line="ctx.line"
      :short="short"
    />
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
