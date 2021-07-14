<template>
  <template v-if="item_name">
    <h2>{{ item_name }} - Metadata</h2>
    <dictionary-table
      :dict="happi_item_info"
      :cls="'metadata'"
      :skip_keys="[]"
      />

    <h2>{{ item_name }} - Related Records</h2>
    <ol>
      <template v-for="record in happi_item_related_records" :key="record">
        <li>
          <router-link :to="`/whatrec/${record}/${record}`">{{record}}</router-link>
        </li>
      </template>
    </ol>
  </template>
  <template v-else>
    <DataTable
        id="happi_table"
        :value="happi_items"
        dataKey="name"
        filterDisplay="row"
        v-model:filters="filters"
        :globalFilterFields="global_filter_fields"
    >
      <template #header>
        <div class="p-d-flex p-jc-between">
          <MultiSelect
            :modelValue="selected_columns"
            :options="columns" optionLabel="header"
            @update:modelValue="onToggle"
            placeholder="Select Columns"
            style="width: 20em"
          />

          <Button type="button" icon="pi pi-filter-slash" label="Clear"
            class="p-button-outlined" @click="clear_filters()"/>
          <span class="p-input-icon-left">
            <i class="pi pi-search" />
            <InputText v-model="filters['global'].value" placeholder="Search" />
          </span>
        </div>
      </template>
      <Column field="name" header="Name">
        <template #body="{data}">
          <router-link :to="`/happi/${data.name}`">{{data.name}}</router-link>
        </template>
      </Column>
      <Column field="device_class" header="Class">
        <template #body="{data}">
          <div class="tooltip">
            {{ data.device_class.split(".").slice(-1)[0] }}
            <span class="tooltiptext">
              {{ data.device_class }}
            </span>
          </div>

        </template>
      </Column>
      <Column field="prefix" header="Prefix">
        <template #body="{data}">
          <router-link :to="`/whatrec/${data.prefix}*/${data.prefix}`">{{data.prefix}}</router-link>
        </template>
      </Column>
      <Column field="active" header="Active">
        <template #body="{data}">
          <i :class="['pi', data.active ? 'pi-check' : 'pi-times']" />
        </template>
      </Column>
      <Column v-for="(col, index) of selected_columns"
        :field="col.field" :header="col.header"
        :key="col.field + '_' + index"
        >
      </Column>
    </DataTable>
  </template>
</template>

<script>
import { mapState } from 'vuex';

import Button from 'primevue/button';
import Column from 'primevue/column';
import DataTable from 'primevue/datatable';
// import Dropdown from 'primevue/dropdown';
import InputText from 'primevue/inputtext';
import MultiSelect from 'primevue/multiselect';
import {FilterMatchMode} from 'primevue/api';

import DictionaryTable from '../components/dictionary-table.vue'

export default {
  name: 'HappiView',
  components: {
    Button,
    Column,
    DataTable,
    DictionaryTable,
    // Dropdown,
    InputText,
    MultiSelect,
  },
  props: {
    item_name: String,
  },
  data() {
    return {
      filters: null,
      selected_columns: null,
    }
  },
  computed: {
    happi_item_related_records () {
      if (!this.item_name || !this.happi_info_ready) {
        return [];
      }
      let records = this.item_to_records[this.item_name] || [];
      return records.sort();
    },
    item_to_records () {
      if (!this.happi_info_ready) {
        return {};
      }
      return this.happi_info.metadata.item_to_records;
    },
    happi_item_info () {
      if (!this.item_name || !this.happi_items || !this.happi_info_ready) {
        return {
          "error": "Unknown item name",
        };
      }
      return this.happi_info.metadata.item_to_metadata[this.item_name];
    },
    happi_items () {
      if (Object.keys(this.happi_info).length == 0) {
        return [];
      }
      return Object.values(this.happi_info.metadata.item_to_metadata);
    },

    global_filter_fields () {
      let fields = ["name", "device_class", "prefix"];
      for (const col of this.selected_columns) {
        fields.push(col.field);
      }
      return fields;
    },

    ...mapState({
      happi_info_ready (state) {
        return Object.keys(state.plugin_info).length > 0;
      },
      happi_info (state) {
        if (!state.plugin_info) {
          return {};
        }
        const happi_info = state.plugin_info.happi || {
            metadata: {item_to_metadata: [], item_name_to_records: []}
          };
        return happi_info;
      },
    }),
  },
  created() {
    this.init_filters();
  },
  mounted() {
    if (!this.happi_info_ready) {
        this.$store.dispatch("update_plugin_info");
    }
  },
  methods: {
    init_filters() {
      this.filters = {
        'global': {value: "", matchMode: FilterMatchMode.CONTAINS},
      };
      this.columns = [
        {field: 'beamline', header: 'Beamline'},
        {field: 'stand', header: 'Stand'},
        {field: 'z', header: 'Z Location (m)'},
        {field: 'last_edit', header: 'Last Edit'},
        {field: 'args', header: 'Arguments'},
        {field: 'kwargs', header: 'Keyword Arguments'},
      ]
      this.selected_columns = this.columns.slice(0, 2);
    },
    clear_filters() {
      this.init_filters();
    },
    onToggle(value) {
      this.selected_columns = this.columns.filter(col => value.includes(col));
    }
  },

}
</script>

<!-- https://www.w3schools.com/css/css_tooltip.asp -->
<style scoped>
.tooltip {
  position: relative;
  display: inline-block;
  border-bottom: 1px dashed black;
}

.tooltip .tooltiptext {
  visibility: hidden;
  width: auto;
  background-color: lightblue;
  color: black;
  text-align: center;
  padding: 5px 0;
  border-radius: 6px;
  position: absolute;
  z-index: 1;
}

.tooltip:hover .tooltiptext {
  visibility: visible;
}
</style>
