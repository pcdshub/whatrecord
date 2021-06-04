<template>
  <DataTable :value="Object.values(fields)">
    <Column field="name" header="Field"></Column>
    <Column field="value" header="Value"></Column>
    <Column field="dtype" header="Type"></Column>
    <Column header="Context">
      <template #body="slotProps">
        <script-context-link :context="slotProps.data.context" :short="true" />
      </template>
    </Column>
  </DataTable>

   <!--
   <script-context-link :context="field.context" :short=true></script-context-link>
   -->
</template>

<script>
import ScriptContextLink from './script-context-link.vue'
import Column from 'primevue/column';
import DataTable from 'primevue/datatable';

export default {
  name: 'RecordFieldTable',
  props: {
    fields: Object
  },
  components: {
    Column,
    DataTable,
    ScriptContextLink,
  },
}
</script>

<style scoped>
</style>
