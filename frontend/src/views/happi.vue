<template>
  <template v-if="item_name">
    <h2>{{ item_name }} - Metadata</h2>
    <dictionary-table
      :dict="happi_item_info"
      :cls="'metadata'"
      :skip_keys="['_whatrecord']"
    />

    <h2>{{ item_name }} - Related Records</h2>
    <template v-if="Object.keys(kind_to_related_records).length > 0">
      <table id="related_records">
        <thead>
          <th>PV</th>
          <th>Attribute</th>
          <th>Kind</th>
        </thead>
        <tbody>
          <template
            v-for="[kind, records] in Object.entries(kind_to_related_records)"
            :key="kind"
          >
            <tr v-for="rec in records" :key="rec.name">
              <td class="pv">
                <router-link
                  :to="{
                    name: 'whatrec',
                    query: {
                      pattern: rec.name,
                      record: rec.name,
                      regex: 'false',
                    },
                  }"
                >
                  {{ rec.name }}
                </router-link>
              </td>
              <td class="pv">
                {{ rec.signal }}
              </td>
              <td class="pv">
                {{ kind.replace(/Kind./g, "") }}
              </td>
            </tr>
          </template>
        </tbody>
      </table>
    </template>
  </template>
  <template v-else>
    <DataTable
      id="happi_table"
      class="p-datatable-sm"
      :value="happi_items"
      dataKey="name"
      filterDisplay="row"
      :paginator="true"
      :rows="150"
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
      <Column field="name" header="Name" :sortable="true" style="width: 12%">
        <template #body="{ data }">
          <router-link :to="{ name: 'happi', query: { item: data.name } }">{{
            data.name
          }}</router-link>
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
      <Column
        field="device_class"
        header="Class"
        :sortable="true"
        style="width: 25%"
      >
        <template #body="{ data }">
          <div class="tooltip">
            {{ data.device_class.split(".").slice(-1)[0] }}
            <span class="tooltiptext">
              {{ data.device_class }}
            </span>
          </div>
        </template>
        <template #filter="{ filterModel, filterCallback }">
          <Dropdown
            v-model="filterModel.value"
            :options="device_classes"
            placeholder="Any"
            class="p-column-filter"
            :showClear="true"
            @change="filterCallback()"
          >
          </Dropdown>
        </template>
      </Column>
      <Column field="prefix" header="Prefix" :sortable="true">
        <template #body="{ data }">
          <router-link
            :to="{
              name: 'whatrec',
              query: {
                pattern: data.prefix + '*',
                record: data.prefix,
                regex: 'false',
              },
            }"
          >
            {{ data.prefix }}
          </router-link>
        </template>
        <template #filter="{ filterModel, filterCallback }">
          <InputText
            type="text"
            v-model="filterModel.value"
            @keydown.enter="filterCallback()"
            class="p-column-filter"
            :placeholder="`Filter by prefix`"
          />
        </template>
      </Column>
      <Column
        field="active"
        header="Active"
        :sortable="true"
        style="width: 13%"
      >
        <template #body="{ data }">
          <i :class="['pi', data.active ? 'pi-check' : 'pi-times']" />
        </template>
        <template #filter="{ filterModel, filterCallback }">
          <Dropdown
            v-model="filterModel.value"
            :options="[false, true]"
            placeholder="Any"
            class="p-column-filter"
            :showClear="true"
            @change="filterCallback()"
          >
          </Dropdown>
        </template>
      </Column>
      <Column
        v-for="(col, index) of selected_columns"
        :field="col.field"
        :header="col.header"
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
      </Column>
    </DataTable>
  </template>
</template>

<script lang="ts">
import { use_configured_store } from "../stores";

import Button from "primevue/button";
import Column from "primevue/column";
import DataTable, { DataTableFilterMetaData } from "primevue/datatable";
import Dropdown from "primevue/dropdown";
import InputText from "primevue/inputtext";
import MultiSelect from "primevue/multiselect";
import { FilterMatchMode } from "primevue/api";

import DictionaryTable from "../components/dictionary-table.vue";
import { PluginResults } from "../types";
import { computed } from "vue";

interface ColumnData {
  field: string;
  header: string;
  style: string;
}

interface HappiItemRecord {
  name: string;
  kind: string;
  signal: string;
}

interface HappiItemWhatrecordAnnotation {
  records: HappiItemRecord[];
}

interface HappiItem {
  device_class: string;
  name: string;
  error?: string;
  _whatrecord: HappiItemWhatrecordAnnotation;
}

const EmptyHappiItem: HappiItem = {
  device_class: "",
  name: "",
  error: "",
  _whatrecord: { records: [] },
};

export default {
  name: "HappiView",
  setup() {
    const store = use_configured_store();
    const plugin_info = computed(() => store.plugin_info.happi ?? null);
    return { store, plugin_info };
  },
  components: {
    Button,
    Column,
    DataTable,
    DictionaryTable,
    Dropdown,
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
    };
  },
  computed: {
    happi_item_info(): HappiItem {
      if (!this.item_name || !this.happi_items || !this.happi_info_ready) {
        return EmptyHappiItem;
      }
      const happi_info: PluginResults | null = this.plugin_info;
      if (!happi_info) {
        return EmptyHappiItem;
      }
      return (
        (happi_info.metadata_by_key[this.item_name] as HappiItem) ??
        EmptyHappiItem
      );
    },
    device_classes() {
      let classes = new Set();
      for (const happi_item of this.happi_items) {
        classes.add(happi_item.device_class);
      }
      return Array.from(classes).sort();
    },
    kind_to_related_records(): Record<string, HappiItemRecord[]> {
      const info = this.happi_item_info;
      if (!info.name) {
        return {};
      }
      let result: Record<string, HappiItemRecord[]> = {};
      for (const rec of info._whatrecord.records) {
        if (rec.kind in result === false) {
          result[rec.kind] = [];
        }
        result[rec.kind].push(rec);
      }
      return result;
    },
    happi_items(): HappiItem[] {
      if (this.plugin_info === null) {
        return [];
      }
      return Object.values(this.plugin_info.metadata_by_key) as HappiItem[];
    },

    global_filter_fields() {
      let fields = ["name", "device_class", "prefix"];
      for (const col of this.selected_columns) {
        fields.push(col.field);
      }
      return fields;
    },
    happi_info_ready() {
      return this.plugin_info !== null;
    },
  },
  created() {
    document.title = `whatrecord? happi plugin`;
    this.init_filters();
  },
  async mounted() {
    if (!this.happi_info_ready) {
      await this.store.update_plugin_info({ plugin: "happi" });
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
    onToggle(value: any) {
      this.selected_columns = value as ColumnData[];
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
