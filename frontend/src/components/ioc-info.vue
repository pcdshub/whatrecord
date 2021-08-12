<template>
  <dictionary-table
    :dict="ioc_info"
    :cls="'metadata'"
    :skip_keys="['commands', 'variables', 'loaded_files']"
  >
  </dictionary-table>

  <details v-if="commands.length">
    <summary>Commands</summary>
    <DataTable :value="commands" dataKey="name">
      <Column field="name" header="Command"  :sortable="true" />
      <Column field="args" header="Arguments" :sortable="true">
        <template #body="{ data }">
          {{ data.args.map(arg => arg.name).join(", ") }}
        </template>
      </Column>

      <Column field="context" header="Context" :sortable="true">
        <template #body="{ data }">
          <script-context-link :context="data.context" :short="5" />
        </template>
      </Column>
    </DataTable>
  </details>

  <template v-if="file_list.length">
    <br />
    Files loaded by {{ ioc_info.name }}: <br />

    <DataTable :value="file_list" dataKey="name">
      <Column field="name" header="File name">
        <template #body="{ data }">
          <router-link
            :to="{ name: 'file', params: { filename: data.name, line: 0 } }"
          >
            {{ data.name }}
          </router-link>
        </template>
      </Column>
      <Column field="hash" header="Hash"> </Column>
    </DataTable>
  </template>
</template>

<script>
import Column from "primevue/column";
import DataTable from "primevue/datatable";

import DictionaryTable from "./dictionary-table.vue";
import ScriptContextLink from "../components/script-context-link.vue";

export default {
  name: "IocInfo",
  components: {
    Column,
    DataTable,
    DictionaryTable,
    ScriptContextLink,
  },
  props: ["ioc_info"],
  data() {
    return {};
  },
  computed: {
    file_list() {
      let files = [];
      for (const [file, hash] of Object.entries(this.ioc_info?.loaded_files || {})) {
        files.push({
          name: file,
          hash: hash,
        });
      }
      return files;
    },

    commands() {
      return Object.values(this.ioc_info?.commands || {});
    },

  },
};
</script>

<style scoped></style>
