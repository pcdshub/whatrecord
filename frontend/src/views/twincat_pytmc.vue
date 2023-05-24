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
          {{ rec }}
        </router-link>
      </li>
    </ul>

    <h3>PLC Information</h3>
    Part of
    <router-link
      :to="{ name: 'twincat_pytmc', query: { plc: selected_item_plc } }"
    >
      {{ selected_item_plc }}
    </router-link>
    <h4>Dependencies</h4>
    <DataTable :value="plc_dependencies" class="p-datatable-sm" dataKey="name">
      <Column field="name" header="Name" />
      <Column field="vendor" header="Vendor" />
      <Column field="version" header="Version" />
    </DataTable>
  </template>
  <template v-else>
    <div id="contents">
      <div id="left" class="column">
        <DataTable
          :value="table_plcs"
          class="p-datatable-sm"
          dataKey="plc"
          v-model:selection="selected_plc"
          @rowSelect="push_route"
          selectionMode="single"
        >
          <Column field="plc" header="PLC" :sortable="true" />
        </DataTable>
      </div>
      <div id="right" class="column">
        <DataTable
          :value="plc_dependencies"
          class="p-datatable-sm"
          dataKey="name"
          style="width: 50%"
        >
          <Column field="name" header="Name" />
          <Column field="vendor" header="Vendor" />
          <Column field="version" header="Version" />
        </DataTable>
        <br />

        <details v-if="nc_axes.length">
          <summary>{{ nc_axes.length }} NC Axes</summary>
          <DataTable :value="nc_axes" class="p-datatable-sm" dataKey="name">
            <Column field="axis_id" header="ID" style="width: 5%" />
            <Column field="name" header="Axis" style="width: 15%">
              <template #body="{ data }">
                "{{ data.name }}" <br />
                <br />
                <script-context-link :context="data.context" :short="1" />
              </template>
            </Column>
            <Column field="units" header="Units" style="width: 5%" />
            <Column field="params" header="Params">
              <template #body="{ data }">
                <dictionary-table
                  :dict="data.params"
                  :cls="'metadata'"
                  :skip_keys="[]"
                />
              </template>
            </Column>
          </DataTable>
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
                <InputText
                  v-model="filters['global'].value"
                  placeholder="Search"
                />
              </span>
            </div>
          </template>
          <Column
            field="name"
            header="Name"
            :sortable="true"
            style="width: 40%"
          >
            <template #body="{ data }">
              <router-link :to="`/twincat_pytmc/${data.full_name}`">{{
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
            field="type"
            header="Type"
            :sortable="true"
            style="width: 15%"
          >
            <template #filter="{ filterModel, filterCallback }">
              <InputText
                type="text"
                v-model="filterModel.value"
                @keydown.enter="filterCallback()"
                class="p-column-filter"
                :placeholder="`Filter by type`"
              />
            </template>
          </Column>
          <Column
            field="context"
            header="Context"
            :sortable="true"
            style="width: 30%"
          >
            <template #body="{ data }">
              <script-context-link :context="data.context" :short="3" />
            </template>
            <template #filter="{ filterModel, filterCallback }">
              <InputText
                type="text"
                v-model="filterModel.value"
                @keydown.enter="filterCallback()"
                class="p-column-filter"
                :placeholder="`Filter by context`"
              />
            </template>
          </Column>
        </DataTable>
      </div>
    </div>
  </template>
</template>

<script>
import { mapState } from "vuex";

import Button from "primevue/button";
import Column from "primevue/column";
import DataTable from "primevue/datatable";
import InputText from "primevue/inputtext";
import { FilterMatchMode } from "primevue/api";

import ScriptContextLink from "../components/script-context-link.vue";
import DictionaryTable from "../components/dictionary-table.vue";

export default {
  name: "TwincatPytmcView",
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
    };
  },
  computed: {
    selected_item_plc() {
      return this.item_name?.split(":")[0] ?? "";
    },

    selected_plc_name() {
      return this.selected_plc?.plc ?? "";
    },

    pytmc_item_info() {
      if (!this.item_name || !this.symbols || !this.info_ready) {
        return {
          error: "",
          _whatrecord: { records: [] },
        };
      }
      return this.plc_info.metadata_by_key[this.item_name];
    },

    related_records() {
      if (!this.item_name) {
        return [];
      }
      let records = [];
      for (const [record, symbols] of Object.entries(
        this.plc_info.record_to_metadata_keys || {}
      )) {
        for (const symbol of symbols) {
          if (symbol == this.item_name) {
            records.push(record);
          }
        }
      }
      return records;
    },

    symbols() {
      return Object.values(this.plc_info?.metadata_by_key ?? {}).map(function (
        info
      ) {
        let obj = { ...info };
        obj.full_name = info.name;
        [obj.plc, obj.name] = obj.full_name.split(":");
        return obj;
      });
    },

    table_plcs() {
      return this.plcs.map((name) => ({ plc: name }));
    },

    nc_axes() {
      return Object.values(this.plc_info?.metadata?.nc?.axes || []);
    },

    plc_dependencies() {
      return Object.values(this.plc_info?.metadata?.dependencies || {});
    },

    ...mapState({
      plcs(state) {
        return state.plugin_nested_info.twincat_pytmc?.keys ?? [];
      },

      plcs_ready(state) {
        return state.plugin_nested_info.twincat_pytmc?.keys.length > 0 ?? false;
      },

      plc_info(state) {
        return (
          state.plugin_nested_info.twincat_pytmc?.info[
            this.selected_plc_name
          ] ?? {}
        );
      },

      info_ready(state) {
        return (
          this.selected_plc_name &&
          this.selected_plc_name in
            (state.plugin_nested_info.twincat_pytmc?.info ?? {})
        );
      },
    }),
  },
  async created() {
    document.title = `WhatRecord? TwinCAT pytmc plugin`;
    this.init_filters();
    this.$watch(
      () => this.$route.params,
      (to_params) => {
        this.from_params(to_params);
      }
    );
    await this.from_params();
  },
  async mounted() {
    if (!this.plcs_ready) {
      await this.$store.dispatch("get_plugin_nested_keys", {
        plugin: "twincat_pytmc",
      });
    }
    await this.from_params();
  },
  methods: {
    async from_params() {
      const route_params = this.$route.params;
      const route_query = this.$route.query;
      const item_plc = route_params.item_name?.split(":")[0];
      const plc = item_plc || route_query.plc;

      if (plc) {
        await this.$store.dispatch("get_plugin_nested_info", {
          plugin: "twincat_pytmc",
          key: plc,
        });
        if (this.selected_plc_name != plc) {
          this.selected_plc = { plc: plc };
        }
      }
    },

    init_filters() {
      this.filters = {
        global: { value: "", matchMode: FilterMatchMode.CONTAINS },
        plc: { value: "", matchMode: FilterMatchMode.CONTAINS },
        name: { value: "", matchMode: FilterMatchMode.CONTAINS },
        type: { value: "", matchMode: FilterMatchMode.CONTAINS },
        context: { value: "", matchMode: FilterMatchMode.CONTAINS },
      };
    },
    clear_filters() {
      this.init_filters();
    },
    push_route() {
      this.$router.push({
        params: {
          item_name: this.item_name ?? "",
        },
        query: {
          plc: this.selected_plc_name,
        },
      });
    },
  },
};
</script>

<style scoped>
#contents {
  display: flex;
  flex-direction: row;
  height: 93vh;
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
  border-right: 1px dotted;
  margin-right: 1em;
}
</style>
