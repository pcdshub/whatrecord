<template>
  <template v-if="item_name">
    <h2>{{ item_name }} - Metadata</h2>
    <dictionary-table
      :dict="plugin_metadata[item_name]"
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
          <router-link
            :to="{ name: 'netconfig', query: { item: data.cn[0] } }"
            >{{ data.cn[0] }}</router-link
          >
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

<script lang="ts">
import { use_configured_store } from "../stores";

import Button from "primevue/button";
import Column from "primevue/column";
import DataTable, { DataTableFilterMetaData } from "primevue/datatable";
/* import Dropdown from "primevue/dropdown"; */
import InputText from "primevue/inputtext";
import MultiSelect from "primevue/multiselect";
import { FilterMatchMode } from "primevue/api";

import DictionaryTable from "../components/dictionary-table.vue";
import { computed } from "vue";

interface ColumnData {
  field: string;
  header: string;
  style: string;
}

export default {
  name: "NetconfigView",
  setup() {
    const store = use_configured_store();
    const plugin_info = computed(() => store.plugin_info.netconfig ?? null);
    return { store, plugin_info };
  },
  components: {
    Button,
    Column,
    DataTable,
    DictionaryTable,
    InputText,
    MultiSelect,
  },
  props: {
    item_name: String,
  },
  data() {
    return {
      filters: {} as Record<string, DataTableFilterMetaData>,
      columns: [] as ColumnData[],
      selected_columns: [] as ColumnData[],
      nice_names: {
        description: "Description",
        location: "Location",
        dc: "Subnet",
        ipHostNumber: "IP Address",
        macAddress: "MAC Address",
        pcNumber: "PC Number",
        o: "Organization",
        ou: "Organization Unit",
      } as Record<string, string>,
    };
  },
  computed: {
    netconfig_items() {
      if (this.plugin_info === null) {
        return [];
      }
      return Object.values(this.plugin_info.metadata);
    },

    global_filter_fields() {
      let fields = ["name", "device_class", "prefix"];
      for (const col of this.selected_columns) {
        fields.push(col.field);
      }
      return fields;
    },
    netconfig_info_ready() {
      return this.plugin_info !== null;
    },
    plugin_metadata(): Record<string, Object> {
      return this.plugin_info.metadata as Record<string, Object>;
    },
  },
  created() {
    document.title = `whatrecord? netconfig ${this.item_name}`;
    this.init_filters();
  },
  async mounted() {
    if (!this.netconfig_info_ready) {
      await this.store.update_plugin_info({ plugin: "netconfig" });
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
        { field: "description", style: "", header: "" },
        { field: "location", style: "", header: "" },
        { field: "dc", style: "", header: "" },
        { field: "ipHostNumber", style: "", header: "" },
        { field: "macAddress", style: "", header: "" },
        { field: "pcNumber", style: "", header: "" },
        { field: "manager", style: "", header: "" },
        { field: "objectClass", style: "", header: "" },
      ];
      for (let col of this.columns) {
        col["header"] = this.nice_names[col.field] ?? col.field;
      }
      this.selected_columns = this.columns.slice(0, 6);
    },
    clear_filters() {
      this.init_filters();
    },
    onToggle(value: any) {
      this.selected_columns = value as ColumnData[];
    },
  },
};
</script>

<style scoped></style>
