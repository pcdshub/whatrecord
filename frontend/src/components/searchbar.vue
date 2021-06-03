<template>
  <form @submit.prevent="do_search" v-on:keyup.enter="do_search">
    <InputText type="text" v-model.trim.lazy="pv_glob" placeholder="*PV Glob*" />
    &nbsp;
    <Button @click="do_search()" label="" icon="pi pi-search" :loading="searching" />
  </form>
  <br/>
  <DataTable :value="table_data" v-model:selection="selected_records" selectionMode="multiple" dataKey="pv"
      @rowSelect="on_new_pvs" @rowUnselect="on_new_pvs">
    <Column field="pv" :header="`PV (${this.displayed_info.glob})`"></Column>
  </DataTable>
</template>

<script>
const axios = require('axios').default;
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
      searching: false,
      max_pvs: 100,
      selected_records: [],
      pv_glob: this.pv_glob_default,
      last_displayed: {
        glob: "",
        list: [],
      },
    }
  },
  computed: mapState({
    glob_to_pvs: state => state.glob_to_pvs,
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
    selected_records_list () {
      // I need to read that JS book...
      let selected_records = [];
      Object.values(this.selected_records).forEach(
        d => selected_records.push(d.pv)
      );
      return selected_records;
    }
  }),

  emits: ["found-pvs", "selected-pvs", "got-record-info"],
  methods: {
    do_search() {
      this.searching = true;
      const search = {
        max_pvs: this.max_pvs,
        pv_glob: this.pv_glob,
      }
      document.title = "WhatRec? " + this.pv_glob;

      axios.get(
        "/api/pv/" + search.pv_glob + "/matches",
        {params:
          {
            max: search.max_pvs
          }
        })
        .then((response) => {
          console.log(response.data);
          let matching_pvs = response.data["matching_pvs"];
          // this.pv_list = matching_pvs;
          this.displayed_results = {
            pv_glob: search.pv_glob,
            pv_list: matching_pvs,
          }
          this.$emit("found-pvs", matching_pvs);
          this.$store.commit(
            "add_search_results",
            {
              pv_glob: search.pv_glob,
              max_pvs: search.max_pvs,
              pv_list: matching_pvs,
            },
          );

        })
        .catch(error => {
          console.log(error)
        })
        .finally(() => {
          this.searching = false;
        });
    },

    on_new_pvs() {
      const selected_records = this.selected_records_list;
      this.$store.commit("set_selected_records", selected_records);
      this.$emit("selected-pvs", selected_records);
      if (selected_records.length == 0) {
        return;
      }

      for (const rec of selected_records) {
        axios.get(
          `/api/pv/${rec}/info`,
          {})
          .then(response => {
            for (const rec in response.data) {
              console.log("Info for PV: " + rec);
              console.log(response.data);
              this.$emit("got-record-info", response.data);

              console.log("Saw " + rec);
              this.$store.commit(
                "add_pv_info",
                {
                  pv: rec,
                  info: response.data[rec],
                },
              );
            }
            // Update the selection list because we have new info
            this.$store.commit("set_selected_records", this.selected_records_list);
          })
          .catch(error => {
            console.log(error)
          });
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
