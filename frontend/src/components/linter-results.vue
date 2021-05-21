<template>
  <div class="result-block">
    Records loaded: {{ load_count }}<br/>
    <br/>
    Macros:<br/>
    <dictionary-table
      :dict="macros"
      :cls="'metadata'"
      :skip_keys="[]">
    </dictionary-table>
  </div>
  <div class="error-block">
    <template v-for="(error, idx) in errors" class="error-block" :key="idx">
      <db-context-link :filename="error.file" :line="error.line"/>
      '{{error.name}}' error: {{error.message}}<br/>
    </template>
    <template v-for="(warning, idx) in warnings" class="error-block" :key="idx">
      <db-context-link :filename="warning.file" :line="warning.line"/>
      '{{warning.name}}' warning: {{warning.message}}<br/>
    </template>
  </div>
</template>

<script>
import DictionaryTable from './dictionary-table.vue';
import DbContextLink from './db-context-link.vue';

export default {
  name: 'LinterResults',
  components: [
    DictionaryTable,
    DbContextLink,
  ],
  props: ["load_count", "errors", "warnings", "macros"],
  beforeCreate() {
    // TODO: I don't think these are circular; why am I running into this?
    this.$options.components.DictionaryTable = require('./dictionary-table.vue').default;
    this.$options.components.DbContextLink = require('./db-context-link.vue').default;
  },
}
</script>

<style scoped>
</style>
