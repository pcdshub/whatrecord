<template>
  <table class="table recordtable">
    <thead class="recordtable">
      <tr>
        <th>Field</th>
        <th>Value</th>
        <th>Type</th>
        <th>Context</th>
      </tr>
    </thead>
    <tbody>
      <tr v-for="field in fields" :key=field.name>
        <td id="field">{{ field.name }}</td>
        <td id="value">{{ field.value }}</td>
        <td id="dtype">{{ field.dtype }}</td>
        <td id="context">
          <script-context-link :context="field.context" :short=true></script-context-link>
        </td>
      </tr>
    </tbody>
  </table>
</template>

<script>
import ScriptContextLink from './script-context-link.vue'

export default {
  name: 'RecordFieldTable',
  props: {
    fields: Object
  },
  components: {
    ScriptContextLink,
  },
}
</script>

<style scoped>
</style>
