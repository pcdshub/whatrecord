<template>
  <form @submit.prevent="do_search" v-on:keyup.enter="do_search">
    <InputText type="text" v-model.trim.lazy="input_record_glob" placeholder="*PV Glob*" />
    &nbsp;
    <Button @click="do_search()" label="" icon="pi pi-search" :loading="searching" />
  </form>
  <br/>
  <DataTable :value="table_data" v-model:selection="table_selection" selectionMode="multiple" dataKey="pv"
      @rowSelect="on_table_selection" @rowUnselect="on_table_selection">
    <Column field="pv" :header="`Results (${this.displayed_info.glob})`"></Column>
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
  props: ["route_record_glob", "route_selected_records"],
  data() {
    return {
      max_pvs: 100,
      table_selection: [],
      input_record_glob: "*",
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
      record_glob: state => state.record_glob,

      displayed_info(state) {
        if (this.input_record_glob in state.glob_to_pvs) {
          this.last_displayed = {
            glob: this.input_record_glob,
            list: state.glob_to_pvs[this.input_record_glob],
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

  created() {
    this.$watch(
      () => this.$route.params, (to_params, previous_params) => {
        console.debug("To", to_params, "From", previous_params);
        this.input_record_glob = to_params.record_glob || "*";
      }
    )
  },

  methods: {
    do_search() {
      document.title = "WhatRec? " + this.input_record_glob;
      this.$store.dispatch("set_record_glob", {"record_glob": this.input_record_glob, "max_pvs": this.max_pvs});
      this.$router.push({
        params: {
          "record_glob": this.input_record_glob,
        }
      });
    },

    on_table_selection() {
      this.$store.dispatch("set_selected_records", {records: this.table_selection_list});
      this.$router.push({
        params: {
          "selected_records": this.table_selection_list.join("|"),
        }
      });
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
