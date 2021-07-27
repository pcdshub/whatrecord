<template>
  <div>
    <DataTable
      :value="gateway_rows"
      dataKey="name"
      filterDisplay="row"
      v-model:filters="filters"
      :globalFilterFields="['pattern', 'full_command', 'error', 'file']"
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
      <Column field="full_command" header="Command">
        <template #filter="{filterModel,filterCallback}">
          <InputText type="text" v-model="filterModel.value" @keydown.enter="filterCallback()" class="p-column-filter"
            :placeholder="`Filter by command`" />
        </template>
      </Column>
      <Column field="pattern" header="Pattern">
        <template #filter="{filterModel,filterCallback}">
          <InputText type="text" v-model="filterModel.value" @keydown.enter="filterCallback()" class="p-column-filter"
            :placeholder="`Filter by pattern`" />
        </template>
        <template #body="{data}">
          <router-link :to='{ name: "whatrec", params: { record_glob: data.pattern }, query: { regex: "true" } }'>
              {{ data.pattern }}
          </router-link>
        </template>
      </Column>
      <Column field="comments" header="Comments">
        <template #filter="{filterModel,filterCallback}">
          <InputText type="text" v-model="filterModel.value" @keydown.enter="filterCallback()" class="p-column-filter"
            :placeholder="`Filter by comments`" />
        </template>
      </Column>
      <Column field="error" header="Error">
        <template #filter="{filterModel,filterCallback}">
          <InputText type="text" v-model="filterModel.value" @keydown.enter="filterCallback()" class="p-column-filter"
            :placeholder="`Filter by error`" />
        </template>
      </Column>
      <Column field="short_fn" header="File name">
        <template #body="{data}">
          <router-link :to="{ name: 'file', params: { filename: data.filename, line: data.line } }">
            {{ data.short_fn }}
          </router-link>
        </template>
        <template #filter="{filterModel,filterCallback}">
          <Dropdown v-model="filterModel.value" :options="filenames"
            placeholder="Any" class="p-column-filter" :showClear="true"
            @change="filterCallback()" >
          </Dropdown>
        </template>
      </Column>
    </DataTable>
  </div>
</template>

<script>
import { mapState } from 'vuex';

import Button from 'primevue/button';
import Column from 'primevue/column';
import DataTable from 'primevue/datatable';
import Dropdown from 'primevue/dropdown';
import InputText from 'primevue/inputtext';
import {FilterMatchMode} from 'primevue/api';

export default {
  name: 'GatewayView',
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
      filters: null,
    }
  },
  computed: {
    filenames () {
      return Object.keys(this.file_to_info).map(
        fn => fn.replace(/^.*[\\/]/, '')
      );
    },
    gateway_rows () {
      let table = [];
      for (const [fn, info] of Object.entries(this.file_to_info)) {
        const short_fn = fn.replace(/^.*[\\/]/, '');
        for (const rule of info.rules) {
          const context = rule.context[0];
          let details = "";
          if (rule.command == "ALLOW") {
            details = rule.access ? rule.access : "(DEFAULT)";
          } else if (rule.command == "DENY") {
            details = rule.hosts ? rule.hosts.join(" ") : "(all hosts)";
          } else if (rule.command == "ALIAS") {
            const access = rule.access ? rule.access : "(DEFAULT)";
            details = `->${rule.pvname} ${access}`;
          }
          table.push(
            {
              short_fn: short_fn,
              pattern: rule.pattern,
              full_command: rule.command + " " + details,
              comments: rule.header,
              filename: fn,
              info: info,
              line: context[1],
              /*
              command: rule.command,
              details: details,
              */
              error: "error" in rule.metadata ? "Error: " + rule.metadata["error"] : "",
            }
          );
        }
      }
      return table;
    },

    ...mapState({
      file_to_info (state) {
        return state.gateway_info || {};
      },

    }),
  },
  created() {
    this.init_filters();
  },
  mounted() {
    if (Object.keys(this.file_to_info).length == 0) {
      this.$store.dispatch("update_gateway_info");
    }
  },

  async beforeRouteUpdate(to, from) {  // eslint-disable-line
    /* this.from_params(to.params); */
  },

  methods: {
    clear_filters() {
      this.init_filters();
    },

    init_filters() {
      this.filters = {
        global: {value: this.filter, matchMode: FilterMatchMode.CONTAINS},
        full_command: {value: null, matchMode: FilterMatchMode.CONTAINS},
        pattern: {value: null, matchMode: FilterMatchMode.CONTAINS},
        error: {value: null, matchMode: FilterMatchMode.CONTAINS},
        comments: {value: null, matchMode: FilterMatchMode.CONTAINS},
        short_fn: {value: null, matchMode: FilterMatchMode.CONTAINS},
      };
    }
  }
}
</script>

<style scoped>
</style>
