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
import ScriptContextLink from './script-context-link.vue';

export default {
  name: 'DictionaryTable',
  props: {
    cls: String,
    dict: Object,
    skip_keys: Array
  },
  components: {
    ScriptContextLink,
  }
}
</script>

<style scoped>
thead tr {
  color: #000000;
  text-align: center;
}

th, td {
  padding: 12px 15px;
}

tbody tr {
  border-bottom: 1px solid #dddddd;
  background-color: #ffffff;
}

tbody tr:nth-of-type(even) {
  background-color: #eeeeee;
}

tbody tr:last-of-type {
  border-bottom: 2px solid black;
}
</style>
