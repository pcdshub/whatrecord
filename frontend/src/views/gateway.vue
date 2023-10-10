<template>
  <div>
    <DataTable
      :value="gateway_rows"
      dataKey="name"
      class="p-datatable-sm"
      filterDisplay="row"
      :paginator="true"
      :rows="200"
      v-model:filters="filters"
      :globalFilterFields="['pattern', 'full_command', 'error', 'file']"
    >
      <template #header>
        <div class="flex justify-content-between">
          <span class="p-input-icon-left">
            <i class="pi pi-search" />
            <InputText
              v-model="filters['name_match'].value"
              placeholder="PV Name match"
            />
          </span>
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
              placeholder="Search All"
            />
          </span>
        </div>
      </template>
      <Column field="full_command" header="Command">
        <template #filter="{ filterModel, filterCallback }">
          <InputText
            type="text"
            v-model="filterModel.value"
            @keydown.enter="filterCallback()"
            class="p-column-filter"
            :placeholder="`Filter by command`"
          />
        </template>
      </Column>
      <Column field="pattern" header="Pattern">
        <template #filter="{ filterModel, filterCallback }">
          <InputText
            type="text"
            v-model="filterModel.value"
            @keydown.enter="filterCallback()"
            class="p-column-filter"
            :placeholder="`Filter by pattern`"
          />
        </template>
        <template #body="{ data }">
          <router-link
            :to="{
              name: 'whatrec',
              query: { pattern: data.pattern, record: [], regex: 'true' },
            }"
          >
            {{ data.pattern }}
          </router-link>
        </template>
      </Column>
      <Column field="comments" header="Comments">
        <template #filter="{ filterModel, filterCallback }">
          <InputText
            type="text"
            v-model="filterModel.value"
            @keydown.enter="filterCallback()"
            class="p-column-filter"
            :placeholder="`Filter by comments`"
          />
        </template>
      </Column>
      <Column field="error" header="Error">
        <template #filter="{ filterModel, filterCallback }">
          <InputText
            type="text"
            v-model="filterModel.value"
            @keydown.enter="filterCallback()"
            class="p-column-filter"
            :placeholder="`Filter by error`"
          />
        </template>
      </Column>
      <Column field="short_fn" header="File name">
        <template #body="{ data }">
          <router-link
            :to="{
              name: 'file',
              query: { filename: data.filename, line: data.line },
            }"
          >
            {{ data.short_fn }}
          </router-link>
        </template>
        <template #filter="{ filterModel, filterCallback }">
          <Dropdown
            v-model="filterModel.value"
            :options="filenames"
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
</template>

<script lang="ts">
import { use_configured_store } from "../stores";

import Button from "primevue/button";
import Column from "primevue/column";
import DataTable, { DataTableFilterMetaData } from "primevue/datatable";
import Dropdown from "primevue/dropdown";
import InputText from "primevue/inputtext";
import { FilterMatchMode, FilterService } from "primevue/api";
import { computed } from "vue";

const RegexFilter = "REGEX_FILTER";

export default {
  name: "GatewayView",
  setup() {
    const store = use_configured_store();
    const gateway_settings = computed(() => store.gateway_info);
    const filename_to_pvlist_info = computed(
      () => store.gateway_info?.pvlists ?? null,
    );
    return { store, gateway_settings, filename_to_pvlist_info };
  },
  components: {
    Button,
    Column,
    DataTable,
    Dropdown,
    InputText,
  },
  props: [],
  data() {
    return {
      filters: {} as Record<string, DataTableFilterMetaData>,
      filter: null,
    };
  },
  computed: {
    filenames(): string[] {
      if (!this.filename_to_pvlist_info) {
        return [];
      }
      return Object.keys(this.filename_to_pvlist_info).map((fn) =>
        fn.replace(/^.*[\\/]/, ""),
      );
    },
    gateway_rows() {
      if (!this.filename_to_pvlist_info) {
        return [];
      }
      let table = [];
      for (const [fn, info] of Object.entries(this.filename_to_pvlist_info)) {
        const short_fn = fn.replace(/^.*[\\/]/, "");
        for (const rule of info.rules) {
          const context = rule.context[0];
          let details = "";
          if (rule.command == "ALLOW") {
            details = rule.access ? rule.access.toString() : "(DEFAULT)";
          } else if (rule.command == "DENY") {
            details = rule.hosts ? rule.hosts.join(" ") : "(all hosts)";
          } else if (rule.command == "ALIAS") {
            const access = rule.access ? rule.access : "(DEFAULT)";
            details = `->${rule.pvname} ${access}`;
          }
          table.push({
            short_fn: short_fn,
            pattern: rule.pattern,
            name_match: rule.pattern, // For the other filter (TODO?)
            full_command: rule.command + " " + details,
            comments: rule.header,
            filename: fn,
            info: info,
            line: context[1],
            /*
              command: rule.command,
              details: details,
              */
            error:
              "error" in rule.metadata
                ? "Error: " + rule.metadata["error"]
                : "",
          });
        }
      }
      return table;
    },
  },
  created() {
    this.init_filters();
  },
  async mounted() {
    FilterService.register(RegexFilter, (value, filter) => {
      if (filter === undefined || filter === null || filter.trim() === "") {
        return true;
      } else if (
        value === undefined ||
        value === null ||
        value.toString() == ".*"
      ) {
        return false;
      }

      const pattern = value.toString();
      try {
        const regex = new RegExp(`^${pattern}$$`, "");
        const match = filter.toString().match(regex);
        return match !== null;
      } catch (error) {
        return false;
      }
    });

    if (this.filename_to_pvlist_info === null) {
      await this.store.update_gateway_info();
    }
  },

  methods: {
    clear_filters() {
      this.init_filters();
    },

    init_filters() {
      this.filters = {
        global: { value: this.filter, matchMode: FilterMatchMode.CONTAINS },
        full_command: { value: null, matchMode: FilterMatchMode.CONTAINS },
        pattern: { value: null, matchMode: FilterMatchMode.CONTAINS },
        error: { value: null, matchMode: FilterMatchMode.CONTAINS },
        comments: { value: null, matchMode: FilterMatchMode.CONTAINS },
        short_fn: { value: null, matchMode: FilterMatchMode.CONTAINS },
        name_match: { value: null, matchMode: RegexFilter },
      };
    },
  },
};
</script>

<style scoped></style>
