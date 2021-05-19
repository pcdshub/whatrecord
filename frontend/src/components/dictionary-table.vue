<template>
  <table class="table" v-if="Object.keys(dict).length > 0">
    <thead :class="cls">
      <tr>
        <th>Item</th>
        <th>Value</th>
      </tr>
    </thead>
    <tbody>
      <tr v-for="(value, key) in dict" :key="key + '-' + value">
        <td :id="key">{{ key }}</td>

        <td v-if="skip_keys.indexOf(key) >= 0">
        </td>
        <td v-else-if="key == 'context'">
          <script-context-link :context=value :short=true></script-context-link>
        </td>
        <td v-else-if="key == 'metadata'">
          <dictionary-table
            :dict="value"
            :cls="'metadata'"
            :skip_keys="[]" />
        </td>
        <td v-else>
          {{ value }}
        </td>
      </tr>
    </tbody>
  </table>
</template>

<script>
export default {
  name: 'DictionaryTable',
  props: {
    cls: String,
    dict: Object,
    skip_keys: Array
  }
}
</script>

<style scoped>
</style>
