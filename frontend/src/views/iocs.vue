<template>
  <DataTable :value="ioc_info" dataKey="name">
    <Column field="name" header="IOC Name"/>
    <Column field="host" header="Host"/>
    <Column field="port" header="Port"/>
    <Column field="description" header="Description"/>
    <Column field="script" header="Script"/>
  </DataTable>
</template>

<script>
import { mapState } from 'vuex'

/* import DictionaryTable from "../components/dictionary-table.vue"; */
import Column from 'primevue/column';
import DataTable from 'primevue/datatable';

export default {
  name: 'WhatRec',
  components: {
    /* DictionaryTable, */
    Column,
    DataTable,
  },
  props: ["glob"],
  computed: mapState({
    ioc_info: state => state.ioc_info,
  }),
  data() {
    return {};
  },
  mounted() {
    this.$store.dispatch("update_ioc_info");
  },
}
</script>

<style scoped>
</style>
