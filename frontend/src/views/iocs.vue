<template>
  <div id="iocs-contents">
    <div id="iocs-left" class="column">
      <DataTable
        id="ioc_info_table"
        :value="ioc_info"
        dataKey="name"
        v-model:selection="selected_iocs"
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
          <div class="p-d-flex p-jc-between">
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
              :to="{ name: 'file', params: { filename: data.script, line: 0 } }"
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
          <div class="p-d-flex p-jc-between">
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
              :to="`/whatrec/${data.record.name}/${data.record.name}`"
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
          v-if="selected_ioc_names.length > 1"
        />
      </DataTable>
    </div>
  </div>
</template>

<script>
import { mapState } from "vuex";

import Button from "primevue/button";
import Column from "primevue/column";
import DataTable from "primevue/datatable";
import Dropdown from "primevue/dropdown";
import InputText from "primevue/inputtext";
import { FilterMatchMode } from "primevue/api";

import IocInfo from "../components/ioc-info.vue";

export default {
  name: "IOCs",
  components: {
    Button,
    Column,
    DataTable,
    Dropdown,
    InputText,
    IocInfo,
  },
  props: ["ioc_filter", "record_filter", "selected_iocs_in"],
  data() {
    return {
      selected_iocs: [],
      ioc_filters: null,
      record_filters: null,
    };
  },
  computed: {
    selected_ioc_names() {
      let iocs = [];
      for (const ioc_info of this.selected_iocs) {
        iocs.push(ioc_info.name);
      }
      return iocs;
    },

    file_list_by_ioc() {
      let files = {};
      for (const ioc_name of this.selected_ioc_names) {
        files[ioc_name] = [];
        if (ioc_name in this.ioc_info_by_name) {
          for (const [file, hash] of Object.entries(
            this.ioc_info_by_name[ioc_name].loaded_files
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
      for (const ioc_name of this.selected_ioc_names) {
        if (ioc_name in this.ioc_info_by_name) {
          info.push(this.ioc_info_by_name[ioc_name]);
        }
      }
      return info;
    },

    ...mapState({
      ioc_info: (state) => state.ioc_info,
      ioc_records: (state) => state.ioc_to_records,

      ioc_info_by_name(state) {
        let iocs = {};
        for (const ioc of state.ioc_info) {
          iocs[ioc.name] = ioc;
        }
        return iocs;
      },

      record_list(state) {
        let records = [];
        for (const ioc_name of this.selected_ioc_names) {
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
      record_types(state) {
        let record_types = new Set();
        for (const ioc_name of this.selected_ioc_names) {
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
    this.from_params(this.$route.params);
  },

  // eslint-disable-next-line no-unused-vars
  async beforeRouteUpdate(to, from) {
    this.from_params(to.params);
  },

  methods: {
    from_params(params) {
      this.$store.dispatch("update_ioc_info");

      const iocs_from_route = params.selected_iocs_in
        ? params.selected_iocs_in.split("|")
        : [];
      if (iocs_from_route != this.selected_iocs_list) {
        this.selected_iocs = [];
        for (const ioc_name of iocs_from_route) {
          if (ioc_name) {
            this.selected_iocs.push({ name: ioc_name });
            if (ioc_name in this.$store.state.ioc_to_records === false) {
              this.$store.dispatch("get_ioc_records", { ioc_name: ioc_name });
            }
          }
        }
      }
      document.title = `WhatRecord? ${iocs_from_route}`;
    },

    new_ioc_selection() {
      this.$router.push({
        params: {
          selected_iocs_in: this.selected_ioc_names.join("|"),
        },
        query: {
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
