<template>
  <form @submit.prevent="do_search" v-on:keyup.enter="do_search">
    <InputText type="text" v-model.trim.lazy="pv_glob" placeholder="*PV Glob*" /><br/>
    <inputNumber v-model.number.lazy="max_pvs" placeholder="200" :min="1" :max="1000" :step="1" /><br/>
    <!-- <p>Query: {{ pv_glob }} (max {{ max_pvs }})</p> -->
    <Button @click="do_search()" label="Search" icon="pi pi-search" :loading="searching" />
    <Button @click="whatrec()" label="whatrecord?"/>
  </form>
  <br/>
  <DataTable :value="table_data" v-model:selection="selected_records" selectionMode="multiple" dataKey="pv"
      @rowSelect="on_new_pvs" @rowUnselect="on_new_pvs">
    <Column field="pv" header="PV"></Column>
  </DataTable>
</template>

<script>
const axios = require('axios').default;

import Button from 'primevue/button';
import Column from 'primevue/column';
import DataTable from 'primevue/datatable';
import InputNumber from 'primevue/inputnumber';
import InputText from 'primevue/inputtext';

export default {
  name: 'Searchbar',
  components: {
    Button,
    Column,
    DataTable,
    InputNumber,
    InputText,
  },
  data() {
    return {
      searching: false,
      max_pvs: 30,
      pv_glob: '*',
      pv_list: [],
      /* selected_records: [], */
      selected_records: [],
      record_info: {},
    }
  },
  computed: {
    table_data() {
      return this.pv_list.map(value => ({"pv": value}));
    }
  },

  emits: ["found-pvs", "selected-pvs", "got-record-info"],
  methods: {
    do_search() {
      this.searching = true;
      document.title = "WhatRec? " + this.pv_glob;
      axios.get(
        "/api/pv/" + this.pv_glob + "/matches",
        {params:
          {
            max: this.max_pvs
          }
        })
        .then(response => {
          console.log(response.data);
          var matching_pvs = response.data["matching_pvs"];
          /*
          this.selected_records = this.selected_records.filter(
            function(v) {return matching_pvs.indexOf(v) >= 0; }
          );
          if (matching_pvs.length > 0 && this.selected_records.length == 0) {
            this.selected_records = [matching_pvs[0]];
            // this.whatrec();
          }
          */
          this.pv_list = matching_pvs;
          this.$emit("found-pvs", self.pv_list);
        })
        .catch(error => {
          console.log(error)
        })
        .finally(() => {
          this.searching = false;
        });
    },

    whatrec() {
      if (this.selected_records.length == 0) {
        return;
      }

      var selected_records = [];

      // I need to read that JS book...
      Object.values(this.selected_records).forEach(
        d => selected_records.push(d.pv)
      );

      axios.get(
        "/api/pv/" + selected_records.join("|") + "/info",
        {})
        .then(response => {
          console.log("Info for PVs: " + this.selected_records);
          console.log(response.data);
          this.record_info = response.data;
          this.$emit("got-record-info", this.record_info);
        })
        .catch(error => {
          console.log(error)
        });
    },

    on_new_pvs() {
      this.$emit("selected-pvs", this.selected_records);
    },

  },
}
</script>

<style>
</style>
