<template>
  <DataTable
    class="p-datatable-sm"
    :value="duplicate_table"
    dataKey="name"
    filterDisplay="row"
    v-model:filters="filters"
    :globalFilterFields="['name', 'iocs']"
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
          <InputText v-model="filters['global'].value" placeholder="Search" />
        </span>
      </div>
    </template>
    <Column field="name" header="Name" :sortable="true">
      <template #body="{ data }">
        <router-link
          :to="{
            name: 'whatrec',
            params: { record_glob: data.name, selected_records: data.name },
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
    <Column field="iocs" header="IOCs" :sortable="true">
      <template #body="{ data }">
        <template v-for="ioc in data.iocs" :key="ioc">
          <router-link
            :to="{ name: 'iocs', params: { selected_iocs_in: ioc } }"
            >{{ ioc }}</router-link
          >
          <br />
        </template>
      </template>
      <template #filter="{ filterModel, filterCallback }">
        <InputText
          type="text"
          v-model="filterModel.value"
          @keydown.enter="filterCallback()"
          class="p-column-filter"
          :placeholder="`Filter by ioc`"
        />
      </template>
    </Column>
  </DataTable>
</template>

<script>
import { mapState } from "vuex";

import Button from "primevue/button";
import Column from "primevue/column";
import DataTable from "primevue/datatable";
import InputText from "primevue/inputtext";
import { FilterMatchMode } from "primevue/api";

export default {
  name: "DuplicateView",
  components: {
    Button,
    Column,
    DataTable,
    InputText,
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
    duplicate_table() {
      return Object.entries(this.duplicates).map(([record, iocs]) => ({
        name: record,
        iocs: iocs,
      }));
    },
    ...mapState({
      duplicates_ready(state) {
        return Object.keys(state.duplicates || {}).length > 0;
      },
      duplicates(state) {
        return state.duplicates;
      },
    }),
  },
  created() {
    document.title = `whatrecord? duplicates`;
    this.init_filters();
  },
  mounted() {
    if (!this.duplicates_ready) {
      this.$store.dispatch("update_duplicates");
    }
  },
  methods: {
    init_filters() {
      this.filters = {
        global: { value: "", matchMode: FilterMatchMode.CONTAINS },
        name: { value: "", matchMode: FilterMatchMode.CONTAINS },
        iocs: { value: "", matchMode: FilterMatchMode.CONTAINS },
      };
    },
    clear_filters() {
      this.init_filters();
    },
  },
};
</script>

<style scoped></style>
