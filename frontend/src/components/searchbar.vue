<template>
  <form @submit.prevent="do_search" v-on:keyup.enter="do_search">
    <InputText type="text" v-model.trim.lazy="pv_glob" placeholder="*PV Glob*" />
    &nbsp;
    <Button @click="do_search()" label="" icon="pi pi-search" :loading="searching" />
  </form>
  <br/>
  <DataTable :value="table_data" v-model:selection="table_selection" selectionMode="multiple" dataKey="pv"
      @rowSelect="on_table_selection" @rowUnselect="on_table_selection">
    <Column field="pv" :header="`PV (${this.displayed_info.glob})`"></Column>
  </DataTable>
</template>

<script>
import { mapState } from 'vuex'

import Button from 'primevue/button';
import Column from 'primevue/column';
import DataTable from 'primevue/datatable';
import InputText from 'primevue/inputtext';

export default {
  name: 'Searchbar',
  components: {
    Button,
    Column,
    DataTable,
    InputText,
  },
  props: ["pv_glob_default"],
  data() {
    return {
      max_pvs: 100,
      selected_records: [],
      table_selection: [],
      pv_glob: this.pv_glob_default,
      last_displayed: {
        glob: "",
        list: [],
      },
    }
  },
  computed: {
    table_selection_list() {
      let as_list = [];
      Object.values(this.table_selection).forEach(
        d => as_list.push(d.pv)
      );
      return as_list;
    },

    ...mapState({
      searching: state => state.query_in_progress,
      glob_to_pvs: state => state.glob_to_pvs,
      selected_record_list: state => state.getters.selected_record_list,

      displayed_info(state) {
        if (this.pv_glob in state.glob_to_pvs) {
          this.last_displayed = {
            glob: this.pv_glob,
            list: state.glob_to_pvs[this.pv_glob],
          }
        }
        return this.last_displayed;
      },
      table_data () {
        return this.displayed_info.list.map(value => ({"pv": value}));
      },
    }),
  },

  emits: [],
  methods: {
    do_search() {
      document.title = "WhatRec? " + this.pv_glob;
      this.$store.dispatch("find_pv_matches", {"pv_glob": this.pv_glob, "max_pvs": this.max_pvs});
    },

    on_table_selection() {
      const table_selection_list = this.table_selection_list;
      this.$store.commit("set_selected_records", table_selection_list);
      for (const rec of table_selection_list) {
        if (rec in this.$store.state.record_info === false) {
          this.$store.dispatch("get_record_info", {"record_name": rec});
        }
      }
    },

  },
}
</script>

<style>
.p-datatable-tbody {
    font-family: monospace;
    font-size: 0.9em;
}
</style>
