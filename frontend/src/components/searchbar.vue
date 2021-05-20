<template>
  <div class="sidebar-page">
    <Sidebar visible="true" position="left" :showCloseIcon="false" :dismissable="false">
      <form @submit.prevent="search">
        <InputText type="text" v-model.trim.lazy="pv_glob" placeholder="*PV Glob*" /><br/>
        <inputNumber v-model.number.lazy="max_pvs" placeholder="200" :min="1" :max="1000" :step="1" /><br/>
        <!-- <p>Query: {{ pv_glob }} (max {{ max_pvs }})</p> -->
        <Button @click="search()" label="Search" icon="pi pi-search" :loading="searching" />
        <Button @click="whatrec()" label="whatrecord?"/>
      </form>
      <br/>
      <DataTable :value=table_data>
        <Column field="pv" header="PV"></Column>
      </DataTable>
    </Sidebar>
  </div>
</template>

<script>
const axios = require('axios').default;

import Button from 'primevue/button';
import Column from 'primevue/column';
import DataTable from 'primevue/datatable';
import InputNumber from 'primevue/inputnumber';
import InputText from 'primevue/inputtext';
import Sidebar from 'primevue/sidebar';

export default {
  name: 'Searchbar',
  components: {
    Button,
    Column,
    DataTable,
    InputNumber,
    InputText,
    Sidebar,
  },
  data() {
    return {
      searching: false,
      max_pvs: 30,
      pv_glob: '*',
      pv_list: [],
      selected_pvs: [],
    }
  },
  computed: {
    table_data() {
      return this.pv_list.map(value => ({"pv": value}));
    }
  },
  methods: {
    search() {
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
          this.selected_pvs = this.selected_pvs.filter(
            function(v) {return matching_pvs.indexOf(v) >= 0; }
          );
          if (matching_pvs.length > 0 && this.selected_pvs.length == 0) {
            this.selected_pvs = [matching_pvs[0]];
            // this.whatrec();
          }
          this.pv_list = matching_pvs;
        })
        .catch(error => {
          console.log(error)
        })
        .finally(() => {
          this.searching = false;
        });
    }
  },
}
</script>

<style>
</style>
