<template>
  <template v-if="item_name">
    <h2>{{ item_name }} - Metadata</h2>
    <dictionary-table
      :dict="pytmc_item_info"
      :cls="'metadata'"
      :skip_keys="['_whatrecord']"
      />

    <h3>Related Records</h3>
    <ul>
      <li v-for="rec of related_records" :key="rec">
        <router-link :to="`/whatrec/${rec}/${rec}`">
          {{rec}}
        </router-link>
      </li>
    </ul>
  </template>
  <template v-else>
    <div id="contents">
      <div id="left" class="column">
        <DataTable
          :value="table_plcs"
          class="p-datatable-sm"
          dataKey="name"
          filterDisplay="row"
          v-model:selection="selected_plc"
          @rowSelect="push_route"
          selectionMode="single"
          :globalFilterFields="['name']"
        >
          <Column field="plc" header="PLC" :sortable="true" />
        </DataTable>
      </div>
      <div id="right" class="column">
        <details>
          <summary>Dependencies</summary>
          <dictionary-table
            :dict="plc_dependencies"
            :cls="'metadata'"
            :skip_keys="[]"
            />
        </details>
        <br />

        <DataTable
          :value="symbols"
          class="p-datatable-sm"
          dataKey="name"
          filterDisplay="row"
          v-model:filters="filters"
          :globalFilterFields="['name', 'type', 'context']"
          :paginator="true"
          :rows="400"
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
          <Column field="name" header="Name" :sortable="true" style="width: 40vw">
            <template #body="{data}">
              <router-link :to="`/twincat_pytmc/${data.full_name}`">{{data.name}}</router-link>
            </template>
            <template #filter="{filterModel,filterCallback}">
              <InputText type="text" v-model="filterModel.value" @keydown.enter="filterCallback()" class="p-column-filter"
                :placeholder="`Filter by name`" />
            </template>
          </Column>
          <Column field="type" header="Type" :sortable="true" style="width: 15vw">
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
      </div>
    </div>
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
import DictionaryTable from '../components/dictionary-table.vue'

export default {
  name: 'TwincatPytmcView',
  components: {
    Button,
    Column,
    DataTable,
    DictionaryTable,
    InputText,
    ScriptContextLink,
  },
  props: {
    item_name: String,
  },
  data() {
    return {
      filters: null,
      selected_plc: null,
    }
  },
  computed: {
    selected_plc_name() {
      return this.selected_plc ? this.selected_plc.plc : "";
    },

    pytmc_item_info () {
      if (!this.item_name || !this.symbols || !this.info_ready) {
        return {
          "error": "",
          "_whatrecord": {"records": []},
        };
      }
      return this.plc_info.metadata_by_key[this.item_name];
    },
    record_to_metadata_keys() {
      if (!this.info_ready) {
        return {};
      }
      return this.plc_info.record_to_metadata_keys || {};
    },
    related_records() {
      if (!this.item_name) {
        return [];
      }
      let records = [];
      for (const [record, symbols] of Object.entries(this.record_to_metadata_keys)) {
        for (const symbol of symbols) {
          if (symbol == this.item_name) {
            records.push(record);
          }
        }
      }
      return records;
    },
    symbols () {
      if (Object.keys(this.plc_info).length == 0) {
        return [];
      }
      return Object.values(this.plc_info.metadata_by_key).map(
        function (info) {
          let obj = { ...info };
          obj.full_name = info.name;
          [obj.plc, obj.name] = obj.full_name.split(":");
          return obj;
        }
      );
    },

    table_plcs () {
      return this.plcs.map(
        (name) => ({ plc: name })
      );
    },

    plc_dependencies () {
      if (!this.info_ready) {
        return {};
      }
      return this.plc_info.metadata.dependencies;
    },

    ...mapState({
      plcs (state) {
        if (!this.plcs_ready) {
          return [];
        }
        return state.plugin_nested_info.twincat_pytmc.keys;
      },

      plcs_ready (state) {
        const nested_info = state.plugin_nested_info;
        const pytmc_info = nested_info.twincat_pytmc;
        return pytmc_info && pytmc_info.keys.length;
      },

      plc_info (state) {
        if (!this.info_ready) {
          return {};
        }
        const pytmc_info = state.plugin_nested_info.twincat_pytmc;
        return pytmc_info.info[this.selected_plc_name];
      },

      info_ready (state) {
        const nested_info = state.plugin_nested_info;
        const pytmc_info = nested_info.twincat_pytmc;
        return (this.selected_plc_name && pytmc_info && this.selected_plc_name in pytmc_info.info);
      },

    }),
  },
  async created() {
    document.title = `WhatRecord? TwinCAT pytmc plugin`;
    this.init_filters();
    this.$watch(
      () => this.$route.params, to_params => {
        this.from_params(to_params);
      }
    )
    await this.from_params();
  },
  async mounted() {
    if (!this.plcs_ready) {
      await this.$store.dispatch("get_plugin_nested_keys", { plugin: "twincat_pytmc" });
    }
    await this.from_params();
  },
  methods: {
    async from_params() {
      const route_query = this.$route.query;
      const plc = route_query.plc || "";
      const item_name = route_query.item_name || "";
      await this.$store.dispatch(
        "get_plugin_nested_info", {
          plugin: "twincat_pytmc",
          key: plc,
        }
      );
      this.selected_plc = { plc: plc };
    },

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
    push_route() {
      this.$router.push({
        query: {
          plc: this.selected_plc_name,
          item_name: this.item_name,
        },
      });
    },

  },

}
</script>

<style scoped>
#contents {
  display: flex;
  flex-direction: row;
  height: 94vh;
  justify-content: flex-start;
  overflow-y: scroll;
}

.column {
  display: flex;
  flex-direction: column;
  overflow-y: scroll;
}

#left {
  min-width: 15vw;
  max-width: 17vw;
  max-height: 97vh;
}
</style>
