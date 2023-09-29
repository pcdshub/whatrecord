<template>
  <template v-if="item_name">
    <h2>{{ item_name }} - Metadata</h2>
    <dictionary-table
      :dict="epicsarch_metadata[item_name]"
      :cls="'metadata'"
      :skip_keys="[]"
    />
  </template>
  <template v-else>
    <div id="epicsarch-contents">
      <div id="epicsarch-left" class="column">
        <DataTable
          id="file_table"
          :paginator="true"
          :rows="300"
          :value="epicsarch_file_table"
          @rowSelect="new_file_selection"
          class="p-datatable-sm"
          dataKey="name"
          filterDisplay="row"
          selectionMode="single"
          v-model:filters="file_filters"
          v-model:selection="selected_file"
          :globalFilterFields="['name']"
        >
          <template #header>
            <div class="flex justify-content-between">
              <Button
                type="button"
                icon="pi pi-filter-slash"
                label="Clear"
                class="p-button-outlined"
                @click="clear_file_filters()"
              />
              <span class="p-input-icon-left">
                <i class="pi pi-search" />
                <InputText
                  v-model="file_filters['global'].value"
                  placeholder="Search"
                />
              </span>
            </div>
          </template>
          <Column field="name" header="Filename" :sortable="true" />
        </DataTable>
      </div>
      <div id="epicsarch-right" class="column">
        <details v-if="file_warnings">
          <summary>Warnings ({{ file_warnings.length }})</summary>
          <template v-for="warning in file_warnings">
            <dictionary-table
              :dict="warning"
              :cls="'metadata'"
              :skip_keys="[]"
              :key="warning.context.toString()"
              v-if="file_warnings"
            />
          </template>
        </details>
        <details v-if="file_info?.loaded_files">
          <summary>
            Loaded files ({{ Object.keys(file_info.loaded_files).length }})
          </summary>
          <ul>
            <li v-for="file in Object.keys(file_info.loaded_files)" :key="file">
              <script-context-link :context="[[file, 0]]" prefix="" />
            </li>
          </ul>
        </details>
        <DataTable
          :value="file_info.pvs"
          dataKey="record.name"
          class="p-datatable-sm"
          :paginator="true"
          :rows="200"
          v-model:filters="info_filters"
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
                @click="clear_file_filters()"
              />
              <span class="p-input-icon-left">
                <i class="pi pi-search" />
                <InputText
                  v-model="info_filters['global'].value"
                  placeholder="Search"
                />
              </span>
            </div>
          </template>
          <Column field="name" header="PV">
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
          <Column
            field="alias"
            header="Alias"
            :sortable="true"
            style="width: 30%"
          >
            <template #filter="{ filterModel, filterCallback }">
              <InputText
                type="text"
                v-model="filterModel.value"
                @keydown.enter="filterCallback()"
                class="p-column-filter"
                :placeholder="`Filter by alias`"
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
          <Column field="provider" header="Provider" style="width: 10%">
            <template #body="{ data }">
              {{ data.provider }}
            </template>
            <template #filter="{ filterModel, filterCallback }">
              <Dropdown
                v-model="filterModel.value"
                :options="['ca', 'pva']"
                placeholder="Any"
                class="p-column-filter"
                :showClear="true"
                @change="filterCallback()"
              >
              </Dropdown>
            </template>
          </Column>
        </DataTable>
      </div>
    </div>
  </template>
</template>

<script lang="ts">
import { use_configured_store } from "../stores";

import Button from "primevue/button";
import Column from "primevue/column";
import DataTable, { DataTableFilterMetaData } from "primevue/datatable";
import Dropdown from "primevue/dropdown";
import InputText from "primevue/inputtext";
import { FilterMatchMode } from "primevue/api";

import ScriptContextLink from "../components/script-context-link.vue";
import DictionaryTable from "../components/dictionary-table.vue";
import { computed } from "vue";
import { FullLoadContext } from "@/types";
import { LocationQueryRaw } from "vue-router";

interface ColumnData {
  name: string;
  filename: string;
}

interface Comment {
  context: FullLoadContext;
  text: string;
}

interface Warning {
  context: FullLoadContext;
  type_: string;
  text: string;
}

interface DaqPV {
  context: FullLoadContext;
  name: string;
  alias: string;
  provider: string;
  comments: Comment[];
}

interface EpicsArchMetadata {
  pvs: Record<string, DaqPV>;
  aliases: Record<string, string>;
  warnings: Warning[];
  filename: string | null;
  loaded_files: Record<string, string>;
}

interface Query {
  selected_file?: string;
  file_filter?: string;
  record_filter?: string;
}

export default {
  name: "NetconfigView",
  setup() {
    const store = use_configured_store();
    const plugin_info = computed(() => store.plugin_info.epicsarch ?? null);
    return { store, plugin_info };
  },
  components: {
    Button,
    Column,
    DataTable,
    DictionaryTable,
    Dropdown,
    InputText,
    ScriptContextLink,
  },
  props: {
    item_name: String,
  },
  data() {
    return {
      file_filters: {} as Record<string, DataTableFilterMetaData>,
      info_filters: {} as Record<string, DataTableFilterMetaData>,
      selected_columns: [] as ColumnData[],
      selected_file: { name: "", filename: "" } as ColumnData,
    };
  },
  computed: {
    epicsarch_file_table() {
      return this.epicsarch_files.map((filename) =>
        this.filename_to_table(filename),
      );
    },

    epicsarch_files() {
      if (!this.epicsarch_info_ready) {
        return [];
      }
      return Object.keys(this.plugin_info.metadata_by_key);
    },

    file_warnings() {
      return this.file_info?.warnings || [];
    },
    file_info() {
      const filename = this.selected_file?.filename;
      if (!this.epicsarch_info_ready || !filename) {
        return {
          pvs: [],
        };
      }

      const metadata = this.plugin_info.metadata_by_key[
        filename
      ] as EpicsArchMetadata;
      return {
        pvs: Object.values(metadata.pvs),
        warnings: metadata.warnings,
        loaded_files: metadata.loaded_files,
        aliases: metadata.aliases,
        filename: metadata.filename,
      };
    },

    epicsarch_metadata() {
      return (this.plugin_info?.metadata as Record<string, Object>) ?? null;
    },
    epicsarch_info_ready() {
      return this.plugin_info !== null;
    },
  },
  created() {
    document.title = `whatrecord? epicsArch ${this.item_name}`;
    this.init_filters();
  },
  async mounted() {
    if (!this.epicsarch_info_ready) {
      await this.store.update_plugin_info({ plugin: "epicsarch" });
    }
    this.from_query(this.$route.query);
  },

  // eslint-disable-next-line no-unused-vars
  async beforeRouteUpdate(to, _from) {
    this.from_query(to.query);
  },

  methods: {
    filename_to_table(filename: string) {
      return {
        name: filename.replace(
          /^.cds.group.pcds.dist.pds.(.*).misc.(.*?)/i,
          "$1 $2",
        ),
        filename: filename,
      };
    },
    init_filters() {
      this.file_filters = {
        global: { value: "", matchMode: FilterMatchMode.CONTAINS },
        name: { value: "", matchMode: FilterMatchMode.CONTAINS },
      };
      this.info_filters = {
        global: { value: "", matchMode: FilterMatchMode.CONTAINS },
        name: { value: "", matchMode: FilterMatchMode.CONTAINS },
        provider: { value: "", matchMode: FilterMatchMode.CONTAINS },
        context: { value: "", matchMode: FilterMatchMode.CONTAINS },
        comments: { value: "", matchMode: FilterMatchMode.CONTAINS },
        alias: { value: "", matchMode: FilterMatchMode.CONTAINS },
      };
    },
    clear_file_filters() {
      this.init_filters();
    },
    onToggle(value: any) {
      this.selected_columns = value as ColumnData[];
    },
    view_as_query(): Query {
      return {
        selected_file: this.selected_file?.filename ?? "",
        file_filter: this.file_filters["global"].value,
        record_filter: this.info_filters["global"].value,
      };
    },
    new_file_selection() {
      this.$router.push({
        query: this.view_as_query() as LocationQueryRaw,
      });
    },

    from_query(query: Query) {
      const selected_filename = query.selected_file;
      if (selected_filename) {
        this.selected_file = this.filename_to_table(
          selected_filename.toString(),
        );
      }
      document.title = `whatrecord? epicsArch ${selected_filename}`;
    },
  },
};
</script>

<style scoped>
#epicsarch-contents {
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

#epicsarch-left {
  max-width: 15%;
  white-space: nowrap;
  border-right: 1px dotted;
}

#epicsarch-right {
  margin: 1em;
  justify-content: stretch;
  max-width: 85%;
}
</style>
