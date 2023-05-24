<template>
  <template v-if="item_name">
    <h2>{{ item_name }} - Metadata</h2>
    <dictionary-table
      :dict="netconfig_info.metadata[item_name]"
      :cls="'metadata'"
      :skip_keys="[]"
    />
  </template>
  <template v-else>
    <DataTable
      id="netconfig_table"
      class="p-datatable-sm"
      :value="netconfig_items"
      dataKey="cn"
      filterDisplay="row"
      :paginator="true"
      :rows="100"
      v-model:filters="filters"
      :globalFilterFields="global_filter_fields"
    >
      <template #header>
        <div class="flex justify-content-between">
          <MultiSelect
            :modelValue="selected_columns"
            :options="columns"
            optionLabel="header"
            @update:modelValue="onToggle"
            placeholder="Select Columns"
            style="width: 20em"
          />

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
      <Column field="cn" header="Name" :sortable="true" style="">
        <template #filter="{ filterModel, filterCallback }">
          <InputText
            type="text"
            v-model="filterModel.value"
            @keydown.enter="filterCallback()"
            class="p-column-filter"
            :placeholder="`Filter by name`"
          />
        </template>
        <template #body="{ data }">
          <router-link :to="`/netconfig/${data.cn[0]}`">{{
            data.cn[0]
          }}</router-link>
          <template v-if="data.cname">
            <br />({{ data.cname.join(", ") }})
          </template>
        </template>
      </Column>
      <Column
        v-for="(col, index) of selected_columns"
        :field="col.field"
        :header="nice_names[col.field] || col.field"
        :key="col.field + '_' + index"
        :sortable="true"
        :style="col.style"
      >
        <template #filter="{ filterModel, filterCallback }">
          <InputText
            type="text"
            v-model="filterModel.value"
            @keydown.enter="filterCallback()"
            class="p-column-filter"
            :placeholder="`Filter`"
          />
        </template>
        <template #body="{ data }">
          {{ data[col.field]?.join(", ") }}
        </template>
      </Column>
    </DataTable>
  </template>
</template>

<script>
import { mapState } from "vuex";

import Button from "primevue/button";
import Column from "primevue/column";
import DataTable from "primevue/datatable";
/* import Dropdown from "primevue/dropdown"; */
import InputText from "primevue/inputtext";
import MultiSelect from "primevue/multiselect";
import { FilterMatchMode } from "primevue/api";

import DictionaryTable from "../components/dictionary-table.vue";

export default {
  name: "NetconfigView",
  components: {
    Button,
    Column,
    DataTable,
    DictionaryTable,
    /* Dropdown, */
    InputText,
    MultiSelect,
  },
  props: {
    item_name: String,
  },
  data() {
    return {
      filters: null,
      selected_columns: null,
      nice_names: {
        description: "Description",
        location: "Location",
        dc: "Subnet",
        ipHostNumber: "IP Address",
        macAddress: "MAC Address",
        pcNumber: "PC Number",
        o: "Organization",
        ou: "Organization Unit",
      },
    };
  },
  computed: {
    netconfig_items() {
      if (Object.keys(this.netconfig_info).length == 0) {
        return [];
      }
      return Object.values(this.netconfig_info.metadata);
    },

    global_filter_fields() {
      let fields = ["name", "device_class", "prefix"];
      for (const col of this.selected_columns) {
        fields.push(col.field);
      }
      return fields;
    },
    ...mapState({
      netconfig_info_ready(state) {
        return Object.keys(state.plugin_info.netconfig || {}).length > 0;
      },
      netconfig_info(state) {
        if (!state.plugin_info) {
          return {};
        }
        const netconfig_info = state.plugin_info.netconfig || {
          metadata: {},
        };
        return netconfig_info;
      },
    }),
  },
  created() {
    document.title = `WhatRecord? netconfig ${this.item_name}`;
    this.init_filters();
  },
  mounted() {
    if (!this.netconfig_info_ready) {
      this.$store.dispatch("update_plugin_info", { plugin: "netconfig" });
    }
  },
  methods: {
    init_filters() {
      this.filters = {
        global: { value: "", matchMode: FilterMatchMode.CONTAINS },
        cn: { value: "", matchMode: FilterMatchMode.CONTAINS },
        device_class: { value: "", matchMode: FilterMatchMode.CONTAINS },
        description: { value: "", matchMode: FilterMatchMode.CONTAINS },
        location: { value: "", matchMode: FilterMatchMode.CONTAINS },
        dc: { value: "", matchMode: FilterMatchMode.CONTAINS },
        ipHostNumber: { value: "", matchMode: FilterMatchMode.CONTAINS },
        macAddress: { value: "", matchMode: FilterMatchMode.CONTAINS },
        pcNumber: { value: "", matchMode: FilterMatchMode.CONTAINS },
        manager: { value: "", matchMode: FilterMatchMode.CONTAINS },
        objectClass: { value: "", matchMode: FilterMatchMode.CONTAINS },
      };
      this.columns = [
        { field: "description", style: "" },
        { field: "location", style: "" },
        { field: "dc", style: "" },
        { field: "ipHostNumber", style: "" },
        { field: "macAddress", style: "" },
        { field: "pcNumber", style: "" },
        { field: "manager", style: "" },
        { field: "objectClass", style: "" },
      ];
      for (let col of this.columns) {
        col["header"] = this.nice_names[col.field] ?? col.field;
      }
      this.selected_columns = this.columns.slice(0, 6);
    },
    clear_filters() {
      this.init_filters();
    },
    onToggle(value) {
      this.selected_columns = value;
    },
  },
};
</script>

<style scoped></style>
