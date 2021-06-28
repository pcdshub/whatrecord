<template>
  <template v-if="item_name">
    <h2>{{ item_name }} - Metadata</h2>
    <dictionary-table
      :dict="happi_item_info"
      :cls="'metadata'"
      :skip_keys="[]"
      />

    <h2>{{ item_name }} - Related Records</h2>
    <ol>
      <template v-for="record in happi_item_related_records" :key="record">
        <li>
          <router-link :to="`/whatrec/${record}/${record}`">{{record}}</router-link>
        </li>
      </template>
    </ol>
  </template>
  <template v-else>
    <DataTable
        id="happi_table"
        :value="happi_items"
        dataKey="name"
        filterDisplay="row"
        v-model:filters="filters"
        :globalFilterFields="['name', 'beamline', 'device_class', 'prefix']"
    >
      <template #header>
        <div class="p-d-flex p-jc-between">
          <Button type="button" icon="pi pi-filter-slash" label="Clear" class="p-button-outlined" @click="clear_filters()"/>
          <span class="p-input-icon-left">
            <i class="pi pi-search" />
            <InputText v-model="filters['global'].value" placeholder="Search" />
          </span>
        </div>
      </template>
      <Column field="name" header="Name">
        <template #body="{data}">
          <router-link :to="`/happi/${data.name}`">{{data.name}}</router-link>
        </template>
      </Column>
      <Column field="device_class" header="Class" />
      <Column field="beamline" header="Beamline" />
      <Column field="prefix" header="Prefix">
        <template #body="{data}">
          <router-link :to="`/whatrec/${data.prefix}*/${data.prefix}`">{{data.prefix}}</router-link>
        </template>
      </Column>
      <Column field="stand" header="Stand" />
      <Column field="active" header="Active" />
    </DataTable>
  </template>
</template>

<script>
import { mapState } from 'vuex';

import Button from 'primevue/button';
import Column from 'primevue/column';
import DataTable from 'primevue/datatable';
// import Dropdown from 'primevue/dropdown';
import InputText from 'primevue/inputtext';
import {FilterMatchMode} from 'primevue/api';

import DictionaryTable from '../components/dictionary-table.vue'

export default {
  name: 'HappiView',
  components: {
    Button,
    Column,
    DataTable,
    DictionaryTable,
    // Dropdown,
    InputText,
  },
  props: {
    item_name: String,
  },
  data() {
    return {
      filters: null,
    }
  },
  computed: {
    happi_item_related_records () {
      if (!this.item_name || !this.happi_items || !this.happi_info.metadata.item_to_records) {
        return [];
      }
      return this.happi_info.metadata.item_to_records[this.item_name];
    },
    happi_item_info () {
      if (!this.item_name || !this.happi_items) {
        return {
          "error": "Unknown item name",
        };
      }
      return this.happi_info.metadata.item_to_metadata[this.item_name];
    },
    happi_items () {
      if (!this.happi_info) {
        return [];
      }
      return Object.values(this.happi_info.metadata.item_to_metadata);
    },

    ...mapState({
      happi_info (state) {
        if (!state.plugin_info) {
          return {};
        }
        const happi_info = state.plugin_info.happi || {
            metadata: {item_to_metadata: [], item_name_to_records: []}
          };
        return happi_info;
      },
    }),
  },
  created() {
    this.init_filters();
  },
  mounted() {
    this.$store.dispatch("update_plugin_info");
    console.log("item name", this.item_name);
  },
  methods: {
    init_filters() {
      this.filters = {
        'global': {value: "", matchMode: FilterMatchMode.CONTAINS},
      };
    },
    clear_filters() {
      this.init_filters();
    },

  },

}
</script>

<style>
</style>
