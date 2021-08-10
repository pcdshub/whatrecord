<template>
  <template v-if="item_name">
    <h2>{{ item_name }} - Metadata</h2>
  </template>
  <template v-else>
    <DataTable
      :value="symbols"
      class="p-datatable-sm"
      dataKey="name"
      filterDisplay="row"
      v-model:filters="filters"
      :globalFilterFields="['name', 'type', 'context']"
    >
      <template #header>
        <div class="p-d-flex p-jc-between">
          <Button type="button" icon="pi pi-filter-slash" label="Clear"
            class="p-button-outlined" @click="clear_filters()"/>
          <span class="p-input-icon-left">
            <i class="pi pi-search" />
            <InputText v-model="filters['global'].value" placeholder="Search" />
          </span>
        </div>
      </template>
      <Column field="plc" header="PLC" :sortable="true">
        <template #filter="{filterModel,filterCallback}">
          <InputText type="text" v-model="filterModel.value" @keydown.enter="filterCallback()" class="p-column-filter"
            :placeholder="`Filter by PLC`" />
        </template>
      </Column>
      <Column field="name" header="Name" :sortable="true">
        <template #body="{data}">
          <router-link :to="`/twincat_pytmc/${data.full_name}`">{{data.name}}</router-link>
        </template>
        <template #filter="{filterModel,filterCallback}">
          <InputText type="text" v-model="filterModel.value" @keydown.enter="filterCallback()" class="p-column-filter"
            :placeholder="`Filter by name`" />
        </template>
      </Column>
      <Column field="type" header="Type" :sortable="true">
        <template #filter="{filterModel,filterCallback}">
          <InputText type="text" v-model="filterModel.value" @keydown.enter="filterCallback()" class="p-column-filter"
            :placeholder="`Filter by type`" />
        </template>
      </Column>
      <Column field="context" header="Context" :sortable="true">
        <template #body="{data}">
          <script-context-link :context="data.context" :short="3" />
        </template>
        <template #filter="{filterModel,filterCallback}">
          <InputText type="text" v-model="filterModel.value" @keydown.enter="filterCallback()" class="p-column-filter"
            :placeholder="`Filter by type`" />
        </template>
      </Column>
    </DataTable>
  </template>
</template>

<script>
import { mapState } from 'vuex';

import Button from 'primevue/button';
import Column from 'primevue/column';
import DataTable from 'primevue/datatable';
import InputText from 'primevue/inputtext';
import {FilterMatchMode} from 'primevue/api';

import ScriptContextLink from '../components/script-context-link.vue'

export default {
  name: 'TwincatPytmcView',
  components: {
    Button,
    Column,
    DataTable,
    InputText,
    ScriptContextLink,
  },
  props: {
    item_name: String,
  },
  data() {
    return {
      filters: null,
      selected_columns: null,
    }
  },
  computed: {
    pytmc_item_info () {
      if (!this.item_name || !this.symbols || !this.info_ready) {
        return {
          "error": "",
          "_whatrecord": {"records": []},
        };
      }
      return this.twincat_info.metadata_by_key[this.item_name];
    },
    symbols () {
      if (Object.keys(this.twincat_info).length == 0) {
        return [];
      }
      return Object.values(this.twincat_info.metadata_by_key).map(
        function (info) {
          let obj = { ...info };
          obj.full_name = info.name;
          [obj.plc, obj.name] = obj.full_name.split(":");
          return obj;
        }
      );
    },

    ...mapState({
      info_ready (state) {
        return Object.keys(state.plugin_info.twincat_pytmc || {}).length > 0;
      },
      twincat_info (state) {
        if (!state.plugin_info) {
          return {};
        }
        const twincat_info = state.plugin_info.twincat_pytmc || {
            metadata_by_key: {},
          };
        return twincat_info;
      },
    }),
  },
  created() {
    document.title = `WhatRecord? TwinCAT pytmc plugin`;
    this.init_filters();
  },
  mounted() {
    if (!this.info_ready) {
        this.$store.dispatch("update_plugin_info", { plugin: "twincat_pytmc" });
    }
  },
  methods: {
    init_filters() {
      this.filters = {
        global: {value: "", matchMode: FilterMatchMode.CONTAINS},
        plc: {value: "", matchMode: FilterMatchMode.CONTAINS},
        name: {value: "", matchMode: FilterMatchMode.CONTAINS},
        type: {value: "", matchMode: FilterMatchMode.CONTAINS},
        context: {value: "", matchMode: FilterMatchMode.CONTAINS},
      };
    },
    clear_filters() {
      this.init_filters();
    },
    onToggle(value) {
      this.selected_columns = value;
    }
  },

}
</script>

<style scoped>
</style>
