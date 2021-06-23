<template>
  <div class="p-grid">
    <div class="p-col-4">
      <DataTable id="ioc_info_table" :value="ioc_info" dataKey="name" v-model:selection="selected_iocs"
          selectionMode="multiple" @rowSelect="new_ioc_selection"
          :paginator="true" :rows="300" v-model:filters="ioc_filters"
          filterDisplay="row" :globalFilterFields="['name', 'host', 'port', 'description']"
          >
        <template #header>
          <div class="p-d-flex p-jc-between">
            <Button type="button" icon="pi pi-filter-slash" label="Clear" class="p-button-outlined" @click="clear_ioc_filters()"/>
            <span class="p-input-icon-left">
              <i class="pi pi-search" />
              <InputText v-model="ioc_filters['global'].value" placeholder="Search" />
            </span>
          </div>
        </template>
        <Column field="name" header="IOC Name"/>
        <Column field="host" header="Host"/>
        <!-- <Column field="port" header="Port"/> -->
        <!-- <Column field="description" header="Description"/> -->
        <!-- <Column field="script" header="Script"/> -->
      </DataTable>
    </div>
    <div class="p-col-8">
      <DataTable :value="record_list" dataKey="record.name"
          :paginator="true" :rows="200" v-model:filters="record_filters" filterDisplay="row"
          :globalFilterFields="['record.name', 'record.record_type']">
        <template #header>
          <div class="p-d-flex p-jc-between">
            <Button type="button" icon="pi pi-filter-slash" label="Clear" class="p-button-outlined" @click="clear_record_filters()"/>
            <span class="p-input-icon-left">
              <i class="pi pi-search" />
              <InputText v-model="record_filters['global'].value" placeholder="Search" />
            </span>
          </div>
        </template>
        <Column field="record.name" header="Record">
          <template #body="{data}">
            <router-link :to="`/whatrec/${data.record.name}/${data.record.name}`">{{data.record.name}}</router-link>
          </template>
          <template #filter="{filterModel,filterCallback}">
            <InputText type="text" v-model="filterModel.value" @keydown.enter="filterCallback()" class="p-column-filter"
              :placeholder="`Filter by name`" />
          </template>
        </Column>
        <Column field="record.record_type" header="Record">
          <template #body="{data}">
            {{data.record.record_type}}
          </template>
          <template #filter="{filterModel,filterCallback}">
            <Dropdown v-model="filterModel.value" :options="record_types"
              placeholder="Any" class="p-column-filter" :showClear="true"
              @change="filterCallback()" >
            </Dropdown>
          </template>
        </Column>
        <Column field="ioc_name" header="IOC" />
      </DataTable>
    </div>
  </div>
</template>

<script>
import { mapState } from 'vuex'

import Button from 'primevue/button';
import Column from 'primevue/column';
import DataTable from 'primevue/datatable';
import Dropdown from 'primevue/dropdown';
import InputText from 'primevue/inputtext';
import {FilterMatchMode} from 'primevue/api';

export default {
  name: 'WhatRec',
  components: {
    Button,
    Column,
    DataTable,
    Dropdown,
    InputText,
  },
  props: ["ioc_filter", "record_filter", "selected_iocs_in"],
  data() {
    return {
      selected_iocs: [],
      ioc_filters: null,
      record_filters: null,
    }
  },
  computed: {
    selected_ioc_list () {
      let iocs = [];
      for (const ioc_info of this.selected_iocs) {
        iocs.push(ioc_info.name);
      }
      return iocs;
    },

    ...mapState({
      ioc_info: state => state.ioc_info,
      ioc_records: state => state.ioc_to_records,
      record_list (state) {
        let records = [];
        for (const ioc_name of this.selected_ioc_list) {
          if (ioc_name in state.ioc_to_records) {
            for (const record of state.ioc_to_records[ioc_name]) {
              records.push({
                ioc_name: ioc_name,
                ioc: ioc_name,
                record: record,
              });
            }
          }
        }
        return records;
      },
      record_types (state) {
        let record_types = new Set();
        for (const ioc_name of this.selected_ioc_list) {
          if (ioc_name in state.ioc_to_records) {
            for (const record of state.ioc_to_records[ioc_name]) {
              record_types.add(record.record_type);
            }
          }
        }
        return Array.from(record_types).sort();
      },
    }),
  },
  created() {
    this.init_record_filters();
    this.init_ioc_filters();
  },
  mounted() {
    this.$store.dispatch("update_ioc_info");
    this.check_route_selection(this.$route);
  },

  async beforeRouteUpdate(to, from) {
    // TODO: linter unused vars?
    console.debug("Route from", from, "to", to);
    this.check_route_selection(to);
  },

  methods: {
    check_route_selection(to) {
      let new_selection = []
      const iocs_from_route = to.params.selected_iocs_in ? to.params.selected_iocs_in.split("|") : [];
      for (const ioc_name of iocs_from_route) {
        new_selection.push({"name": ioc_name});
      }
      if (iocs_from_route != this.selected_iocs_list) {
        console.debug("IOCs was:", this.selected_iocs_list, "now:", iocs_from_route);
        this.selected_iocs = new_selection;
        this.new_ioc_selection(null, false);
      }
    },
    new_ioc_selection(event, push_route=true) {
      for (const ioc_name of this.selected_ioc_list) {
        if (ioc_name in this.$store.state.ioc_to_records === false) {
          this.$store.dispatch("get_ioc_records", {ioc_name: ioc_name});
        }
      }
      if (push_route) {
        this.$router.push({
          params: {
            "selected_iocs_in": this.selected_ioc_list.join("|"),
          },
          query: {
            "ioc_filter": this.ioc_filters["global"].value,
            "record_filter": this.record_filters["global"].value,
          }
        });
      }
    },

    clear_ioc_filters() {
      this.init_ioc_filters();
    },

    clear_record_filters() {
      this.init_record_filters();
    },

    init_ioc_filters() {
      this.ioc_filters = {
        'global': {value: this.ioc_filter, matchMode: FilterMatchMode.CONTAINS},
        'name': {value: null, matchMode: FilterMatchMode.CONTAINS},
        'host': {value: null, matchMode: FilterMatchMode.CONTAINS},
        'port': {value: null, matchMode: FilterMatchMode.CONTAINS},
        'description': {value: null, matchMode: FilterMatchMode.CONTAINS},
      };
    },

    init_record_filters() {
      this.record_filters = {
        'global': {value: this.record_filter, matchMode: FilterMatchMode.CONTAINS},
        'record.name': {value: null, matchMode: FilterMatchMode.CONTAINS},
        'record.record_type': {value: null, matchMode: FilterMatchMode.EQUALS},
      };
    }
  }
}
</script>

<style scoped>
</style>
