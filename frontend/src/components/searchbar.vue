<template>
  <form @submit.prevent="do_search" v-on:keyup.enter="do_search">
    <InputText type="text" v-model.trim.lazy="input_record_glob" placeholder="*PV Glob*" />
    &nbsp;
    <Button @click="do_search()" label="" icon="pi pi-search" :loading="searching" />
  </form>
  <DataTable :value="table_data" v-model:selection="table_selection" selectionMode="multiple" dataKey="pv"
      @rowSelect="on_table_selection" @rowUnselect="on_table_selection">
    <Column field="pv" :header="`Results`"></Column>
  </DataTable>
</template>

<script>
import { mapState } from 'vuex'

import Button from 'primevue/button';
import Column from 'primevue/column';
import DataTable from 'primevue/datatable';
import InputText from 'primevue/inputtext';

export default {
  name: 'Searchbar',
  components: {
    Button,
    Column,
    DataTable,
    InputText,
  },
  props: [],
  data() {
    return {
      max_pvs: 100,
      table_selection: [],
      input_record_glob: "*",
      last_displayed: {
        glob: "",
        list: [],
      },
    }
  },
  computed: {
    table_selection_list() {
      let as_list = [];
      Object.values(this.table_selection).forEach(
        d => as_list.push(d.pv)
      );
      return as_list;
    },

    table_data () {
      return this.displayed_info.list.map(value => ({"pv": value}));
    },
    record_glob () {
      return this.$route.params.record_glob || "";
    },
    ...mapState({
      searching: state => state.query_in_progress,

      displayed_info(state) {
        if (this.record_glob in state.glob_to_pvs) {
          this.last_displayed = {
            glob: this.record_glob,
            list: state.glob_to_pvs[this.record_glob],
          }
        }
        return this.last_displayed;
      },
    }),
  },

  emits: [],

  created() {
    this.$watch(
      () => this.$route.params, (to_params) => {
        this.from_route_params(
          to_params.record_glob,
          to_params.selected_records,
        );
      }
    )
  },
  mounted() {
    this.from_route_params(
      this.$route.params.record_glob,
      this.$route.params.selected_records,
    );
  },
  methods: {
    from_route_params (record_glob, selected_records) {
      this.input_record_glob = record_glob || "*";
      document.title = "WhatRecord? " + record_glob;
      this.$store.dispatch(
        "find_record_matches",
        {"record_glob": record_glob, "max_pvs": this.max_pvs}
      );
      this.table_selection = [];
      for (const rec of (selected_records || "").split("|")) {
        if (rec.length > 0) {
          this.$store.dispatch("get_record_info", { record_name: rec });
          this.table_selection.push({pv: rec});
        }
      }
    },
    do_search() {
      this.$router.push({
        params: {
          "record_glob": this.record_glob,
        }
      });
    },

    on_table_selection() {
      this.$router.push({
        params: {
          "selected_records": this.table_selection_list.join("|"),
        }
      });
    },

  },
}
</script>

<style>
</style>
