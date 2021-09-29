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
      dataKey="name"
      filterDisplay="row"
      v-model:filters="filters"
      :globalFilterFields="global_filter_fields"
    >
      <template #header>
        <div class="p-d-flex p-jc-between">
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
        <template #body="{ data }">
          <router-link :to="`/netconfig/${data.cn[0]}`">{{ data.cn[0] }}</router-link>
          <template v-if="data.cname">
            <br/>({{ data.cname.join(", ") }})
          </template>
        </template>
      </Column>
      <Column field="description" header="Description" :sortable="true" style="">
        <template #body="{ data }">
          {{ data.description?.join(", ") }}
        </template>
      </Column>
      <Column field="location" header="Location" :sortable="true" style="">
        <template #body="{ data }">
          {{ data.location?.join(", ") }}
        </template>
      </Column>
      <Column field="dc" header="Subnet" :sortable="true" style="">
        <template #body="{ data }">
          {{ data.dc?.join(", ") }}
        </template>
      </Column>
      <Column field="ipHostNumber" header="IP Address" :sortable="true" style="">
        <template #body="{ data }">
          {{ data.ipHostNumber?.join(", ") }}
        </template>
      </Column>
      <Column field="macAddress" header="MAC Address" :sortable="true" style="">
        <template #body="{ data }">
          {{ data.macAddress?.join(", ") }}
        </template>
      </Column>
      <Column field="pcNumber" header="PC Number" :sortable="true" style="">
        <template #body="{ data }">
          {{ data.pcNumber?.join(", ") }}
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
    document.title = `WhatRecord? netconfig plugin ${this.item_name}`;
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
        name: { value: "", matchMode: FilterMatchMode.CONTAINS },
        device_class: { value: "", matchMode: FilterMatchMode.CONTAINS },
        prefix: { value: "", matchMode: FilterMatchMode.CONTAINS },
        beamline: { value: "", matchMode: FilterMatchMode.CONTAINS },
        stand: { value: "", matchMode: FilterMatchMode.CONTAINS },
        active: { value: "", matchMode: FilterMatchMode.EQUALS },
        z: { value: "", matchMode: FilterMatchMode.CONTAINS },
        last_edit: { value: "", matchMode: FilterMatchMode.CONTAINS },
        args: { value: "", matchMode: FilterMatchMode.CONTAINS },
        kwargs: { value: "", matchMode: FilterMatchMode.CONTAINS },
      };
      this.columns = [
        { field: "beamline", header: "Beamline", style: "width: 10%" },
        { field: "stand", header: "Stand", style: "width: 10%" },
        { field: "z", header: "Z Location (m)", style: "width: 10%" },
        { field: "last_edit", header: "Last Edit", style: "width: 10%" },
        { field: "args", header: "Arguments", style: "width: 15%" },
        { field: "kwargs", header: "Keyword Arguments", style: "width: 15%" },
      ];
      this.selected_columns = this.columns.slice(0, 2);
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

<!-- https://www.w3schools.com/css/css_tooltip.asp -->
<style scoped>
.tooltip {
  position: relative;
  display: inline-block;
  border-bottom: 1px dashed black;
}

.tooltip .tooltiptext {
  visibility: hidden;
  width: auto;
  background-color: lightblue;
  color: black;
  text-align: center;
  padding: 5px 0;
  border-radius: 6px;
  position: absolute;
  z-index: 1;
}

.tooltip:hover .tooltiptext {
  visibility: visible;
}

#related_records {
  border-collapse: collapse;
}

#related_records td,
#related_records th {
  border: 1px solid #ddd;
  padding: 8px;
}

#related_records tr:nth-child(even) {
  background-color: var(--surface-b);
}

#related_records tr:hover {
  background-color: var(--surface-c);
}

#related_records th {
  padding-top: 12px;
  padding-bottom: 12px;
  text-align: center;
  border: 1px solid;
}

#related_records td {
  font-family: monospace;
}
</style>
