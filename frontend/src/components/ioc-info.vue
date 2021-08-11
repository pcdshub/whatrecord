<template>
  <dictionary-table
    :dict="ioc_info"
    :cls="'metadata'"
    :skip_keys="['commands', 'variables', 'loaded_files']"
  >
  </dictionary-table>

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

export default {
  name: "IocInfo",
  components: {
    Column,
    DataTable,
    DictionaryTable,
  },
  props: ["ioc_info"],
  data() {
    return {};
  },
  computed: {
    file_list() {
      let files = [];
      if (!this.ioc_info) {
        return files;
      }
      for (const [file, hash] of Object.entries(this.ioc_info.loaded_files)) {
        files.push({
          name: file,
          hash: hash,
        });
      }
      return files;
    },
  },
};
</script>

<style scoped></style>
