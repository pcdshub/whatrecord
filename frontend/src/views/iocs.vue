<template>
  <div id="iocs-contents">
    <div id="iocs-left" class="column">
      <DataTable
        id="ioc_info_table"
        :value="ioc_info"
        dataKey="name"
        v-model:selection="user_selected_iocs"
        class="p-datatable-sm"
        selectionMode="multiple"
        @rowSelect="new_ioc_selection"
        :paginator="true"
        :rows="300"
        v-model:filters="ioc_filters"
        filterDisplay="row"
        :globalFilterFields="[
          'name',
          'host',
          'port',
          'description',
          'base_version',
        ]"
      >
        <template #header>
          <div class="flex justify-content-between">
            <Button
              type="button"
              icon="pi pi-filter-slash"
              label="Clear"
              class="p-button-outlined"
              @click="clear_ioc_filters()"
            />
            <span class="p-input-icon-left">
              <i class="pi pi-search" />
              <InputText
                v-model="ioc_filters['global'].value"
                placeholder="Search"
              />
            </span>
          </div>
        </template>
        <Column field="name" header="IOC Name" :sortable="true">
          <template #body="{ data }">
            <router-link
              :to="{ name: 'file', query: { filename: data.script, line: 0 } }"
              >{{ data.name }}</router-link
            >
          </template>
        </Column>
        <Column field="host" header="Host" :sortable="true" />
        <Column field="base_version" header="Version" :sortable="true" />
        <!-- <Column field="port" header="Port"/> -->
        <!-- <Column field="description" header="Description"/> -->
        <!-- <Column field="script" header="Script"/> -->
      </DataTable>
    </div>
    <div id="iocs-right" class="column">
      <template v-for="ioc in selected_ioc_infos" :key="ioc.name">
        <details>
          <summary>{{ ioc.name }} information</summary>
          <ioc-info :ioc_info="ioc" />
        </details>
      </template>

      <DataTable
        :value="record_list"
        dataKey="record.name"
        class="p-datatable-sm"
        :paginator="true"
        :rows="200"
        v-model:filters="record_filters"
        filterDisplay="row"
        :globalFilterFields="['record.name', 'record.record_type']"
      >
        <template #header>
          <div class="flex justify-content-between">
            <Button
              type="button"
              icon="pi pi-filter-slash"
              label="Clear"
              class="p-button-outlined"
              @click="clear_record_filters()"
            />
            <span class="p-input-icon-left">
              <i class="pi pi-search" />
              <InputText
                v-model="record_filters['global'].value"
                placeholder="Search"
              />
            </span>
          </div>
        </template>
        <Column field="record.name" header="Record">
          <template #body="{ data }">
            <router-link
              :to="{
                name: 'whatrec',
                query: {
                  pattern: data.record.name,
                  record: data.record.name,
                  use_regex: 'false',
                },
              }"
              >{{ data.record.name }}</router-link
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
        <Column field="record.record_type" header="Record">
          <template #body="{ data }">
            {{ data.record.record_type }}
          </template>
          <template #filter="{ filterModel, filterCallback }">
            <Dropdown
              v-model="filterModel.value"
              :options="record_types"
              placeholder="Any"
              class="p-column-filter"
              :showClear="true"
              @change="filterCallback()"
            >
            </Dropdown>
          </template>
        </Column>
        <Column
          field="ioc_name"
          header="IOC"
          v-if="user_selected_ioc_names.length > 1"
        />
      </DataTable>
    </div>
  </div>
</template>

<script lang="ts">
import { use_configured_store } from "../stores";

import Button from "primevue/button";
import Column from "primevue/column";
import DataTable, { DataTableFilterMetaData } from "primevue/datatable";
import Dropdown from "primevue/dropdown";
import InputText from "primevue/inputtext";
import { FilterMatchMode } from "primevue/api";

import IocInfo from "@/components/ioc-info.vue";
import { computed, nextTick } from "vue";
import { IocMetadata } from "@/types";

interface SelectedIOC {
  // TODO: primevue + typescript?
  name: string;
}

interface FileLoadedInIOC {
  ioc: string;
  name: string;
  hash: string;
}

export default {
  name: "IOCs",
  setup() {
    const store = use_configured_store();
    const ioc_info = computed(() => store.ioc_info);
    const ioc_to_records = computed(() => store.ioc_to_records);
    return { store, ioc_info, ioc_to_records };
  },
  components: {
    Button,
    Column,
    DataTable,
    Dropdown,
    InputText,
    IocInfo,
  },
  props: {
    ioc_filter: {
      type: String,
      required: false,
      default: "",
    },
    record_filter: {
      type: String,
      required: false,
      default: "",
    },
    selected_iocs: {
      type: Array<string>,
      required: false,
      default: [],
    },
  },
  data() {
    return {
      user_selected_iocs: [] as SelectedIOC[],
      ioc_filters: {} as Record<string, DataTableFilterMetaData>,
      record_filters: {} as Record<string, DataTableFilterMetaData>,
    };
  },
  computed: {
    user_selected_ioc_names(): string[] {
      let iocs = [];
      for (const ioc_info of this.user_selected_iocs) {
        iocs.push(ioc_info.name);
      }
      return iocs;
    },

    file_list_by_ioc() {
      let files: Record<string, FileLoadedInIOC[]> = {};
      for (const ioc_name of this.user_selected_ioc_names) {
        files[ioc_name] = [];
        if (ioc_name in this.ioc_info_by_name) {
          for (const [file, hash] of Object.entries(
            this.ioc_info_by_name[ioc_name].loaded_files,
          )) {
            files[ioc_name].push({
              ioc: ioc_name,
              name: file,
              hash: hash,
            });
          }
        }
      }
      return files;
    },

    selected_ioc_infos() {
      let info = [];
      for (const ioc_name of this.user_selected_ioc_names) {
        if (ioc_name in this.ioc_info_by_name) {
          info.push(this.ioc_info_by_name[ioc_name]);
        }
      }
      return info;
    },

    ioc_info_by_name(): Record<string, IocMetadata> {
      let iocs: Record<string, IocMetadata> = {};
      for (const ioc of this.ioc_info ?? []) {
        iocs[ioc.name] = ioc;
      }
      return iocs;
    },

    record_list() {
      let records = [];
      for (const ioc_name of this.user_selected_ioc_names) {
        if (ioc_name in this.ioc_to_records) {
          for (const record of this.ioc_to_records[ioc_name]) {
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
    record_types() {
      let record_types = new Set();
      for (const ioc_name of this.user_selected_ioc_names) {
        if (ioc_name in this.ioc_to_records) {
          for (const record of this.ioc_to_records[ioc_name]) {
            record_types.add(record.record_type);
          }
        }
      }
      return Array.from(record_types).sort();
    },
  },

  created() {
    this.init_record_filters();
    this.init_ioc_filters();
  },
  async mounted() {
    this.update_table_selection(this.selected_iocs);
    await this.update_store();
  },

  async updated() {
    await this.update_store();
  },

  watch: {
    async $route() {
      // Wait until the prop is updated, then update the table DOM:
      await nextTick();
      this.update_table_selection(this.selected_iocs);
    },
  },

  methods: {
    async update_store() {
      await this.store.update_ioc_info();
      if (this.ioc_info === null) {
        return;
      }

      for (const ioc of this.user_selected_iocs) {
        if (ioc.name && ioc.name in this.ioc_info === false) {
          await this.store.get_ioc_records({ ioc_name: ioc.name });
        }
      }
      document.title = `whatrecord? ${this.user_selected_ioc_names}`;
    },

    update_table_selection(iocs: string[]) {
      if (iocs == this.user_selected_ioc_names) {
        return;
      }
      let table_selection = [];
      for (const ioc of iocs) {
        if (ioc.length > 0) {
          table_selection.push({ name: ioc });
        }
      }
      this.user_selected_iocs = table_selection;
    },

    new_ioc_selection() {
      this.$router.push({
        query: {
          ioc: this.user_selected_ioc_names,
          ioc_filter: this.ioc_filters["global"].value,
          record_filter: this.record_filters["global"].value,
        },
      });
    },

    clear_ioc_filters() {
      this.init_ioc_filters();
    },

    clear_record_filters() {
      this.init_record_filters();
    },

    init_ioc_filters() {
      this.ioc_filters = {
        global: { value: this.ioc_filter, matchMode: FilterMatchMode.CONTAINS },
        name: { value: null, matchMode: FilterMatchMode.CONTAINS },
        host: { value: null, matchMode: FilterMatchMode.CONTAINS },
        port: { value: null, matchMode: FilterMatchMode.CONTAINS },
        base_version: { value: null, matchMode: FilterMatchMode.CONTAINS },
        description: { value: null, matchMode: FilterMatchMode.CONTAINS },
      };
    },

    init_record_filters() {
      this.record_filters = {
        global: {
          value: this.record_filter,
          matchMode: FilterMatchMode.CONTAINS,
        },
        "record.name": { value: null, matchMode: FilterMatchMode.CONTAINS },
        "record.record_type": {
          value: null,
          matchMode: FilterMatchMode.EQUALS,
        },
      };
    },
  },
};
</script>

<style scoped>
#iocs-contents {
  flex-direction: row;
  justify-content: stretch;
  display: flex;
  flex-wrap: nowrap;
  height: 97vh;
}

.column {
  display: flex;
  flex-direction: column;
  flex-shrink: 0;
  justify-content: flex-start;
  overflow-y: scroll;
}

#iocs-left {
  max-width: 35%;
  white-space: nowrap;
  border-right: 1px dotted;
}

#iocs-right {
  margin: 1em;
  justify-content: stretch;
  max-width: 65%;
}
</style>
