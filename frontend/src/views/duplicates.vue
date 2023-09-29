<template>
  <DataTable
    class="p-datatable-sm"
    :value="duplicate_table"
    dataKey="name"
    filterDisplay="row"
    v-model:filters="filters"
    :globalFilterFields="['name', 'iocs']"
  >
    <template #header>
      <div class="flex justify-content-between">
        <Button
          type="button"
          icon="pi pi-filter-slash"
          label="Clear"
          class="p-button-outlined"
          @click="clear_filters()"
        />
        <span class="p-input-icon-left">
          <i class="pi pi-search" />
          <InputText v-model="filters['global'].value" placeholder="Search" />
        </span>
      </div>
    </template>
    <Column field="name" header="Name" :sortable="true">
      <template #body="{ data }">
        <router-link
          :to="{
            name: 'whatrec',
            query: {
              pattern: data.name,
              record: data.name,
              regex: 'false',
            },
          }"
          >{{ data.name }}</router-link
        >
      </template>
      <template #filter="{ filterModel, filterCallback }">
        <InputText
          type="text"
          v-model="filterModel.value"
          @keydown.enter="filterCallback()"
          class="p-column-filter"
          :placeholder="`Filter by name`"
        />
      </template>
    </Column>
    <Column field="iocs" header="IOCs" :sortable="true">
      <template #body="{ data }">
        <template v-for="ioc in data.iocs" :key="ioc">
          <router-link :to="{ name: 'iocs', query: { ioc: data.iocs } }">{{
            ioc
          }}</router-link>
          <br />
        </template>
      </template>
      <template #filter="{ filterModel, filterCallback }">
        <InputText
          type="text"
          v-model="filterModel.value"
          @keydown.enter="filterCallback()"
          class="p-column-filter"
          :placeholder="`Filter by ioc`"
        />
      </template>
    </Column>
  </DataTable>
</template>

<script lang="ts">
import { use_configured_store } from "../stores";

import Button from "primevue/button";
import Column from "primevue/column";
import DataTable, { DataTableFilterMetaData } from "primevue/datatable";
import InputText from "primevue/inputtext";
import { FilterMatchMode } from "primevue/api";

export default {
  name: "DuplicateView",
  setup() {
    const store = use_configured_store();
    return { store };
  },
  components: {
    Button,
    Column,
    DataTable,
    InputText,
  },
  props: {
    item_name: String,
  },
  data() {
    return {
      filters: {} as Record<string, DataTableFilterMetaData>,
      selected_columns: null,
    };
  },
  computed: {
    duplicate_table() {
      return Object.entries(this.store.duplicates).map(([record, iocs]) => ({
        name: record,
        iocs: iocs,
      }));
    },
    duplicates_ready() {
      return Object.keys(this.store.duplicates || {}).length > 0;
    },
  },
  created() {
    document.title = `whatrecord? duplicates`;
    this.init_filters();
  },
  async mounted() {
    if (!this.duplicates_ready) {
      await this.store.update_duplicates();
    }
  },
  methods: {
    init_filters() {
      this.filters = {
        global: { value: "", matchMode: FilterMatchMode.CONTAINS },
        name: { value: "", matchMode: FilterMatchMode.CONTAINS },
        iocs: { value: "", matchMode: FilterMatchMode.CONTAINS },
      };
    },
    clear_filters() {
      this.init_filters();
    },
  },
};
</script>

<style scoped></style>
