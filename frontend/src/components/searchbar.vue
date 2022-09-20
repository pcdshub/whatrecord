<template>
  <div class="p-grid option">
    <div class="p-col-6">
      <SelectButton
        v-model="search_mode"
        :options="search_mode_options"
        @click="do_search"
      />
    </div>
  </div>
  <div class="p-grid search">
    <div class="p-col-10">
      <form @submit.prevent="do_search" v-on:keyup.enter="do_search">
        <InputText
          type="text"
          v-model.trim.lazy="input_record_glob"
          placeholder="*PV Glob*"
          class="input_search"
        />
      </form>
    </div>
    <div class="p-col-2">
      <Button @click="do_search()" icon="pi pi-search" :loading="searching" />
    </div>
  </div>
  <DataTable
    :value="table_data"
    v-model:selection="table_selection"
    selectionMode="multiple"
    dataKey="pv"
    class="p-datatable-sm"
    @rowSelect="on_table_selection"
    @rowUnselect="on_table_selection"
  >
    <Column field="pv" :header="`Results`"> </Column>
  </DataTable>
</template>

<script>
import { mapState } from "vuex";

import Button from "primevue/button";
import Column from "primevue/column";
import SelectButton from "primevue/selectbutton";
import DataTable from "primevue/datatable";
import InputText from "primevue/inputtext";

export default {
  name: "Searchbar",
  components: {
    Button,
    Column,
    DataTable,
    SelectButton,
    InputText,
  },
  props: [],
  data() {
    return {
      max_pvs: 200,
      table_selection: [],
      input_record_glob: "*",
      search_mode: "Glob",
      search_mode_options: ["Glob", "Regex"],
    };
  },
  computed: {
    regex() {
      return this.search_mode === "Regex";
    },
    table_selection_list() {
      let as_list = [];
      Object.values(this.table_selection).forEach((d) => as_list.push(d.pv));
      return as_list;
    },

    pattern() {
      return this.$route.params.record_glob || "";
    },
    ...mapState({
      searching: (state) => state.query_in_progress,

      table_data(state) {
        const pattern_to_pvs = this.regex
          ? state.regex_to_pvs
          : state.glob_to_pvs;
        if (this.pattern in pattern_to_pvs) {
          const pvs = pattern_to_pvs[this.pattern];
          return pvs.map((value) => ({ pv: value }));
        }
        return [];
      },
    }),
  },

  emits: [],

  async created() {
    this.$watch(
      () => this.$route.params,
      (to_params) => {
        this.from_route(to_params, this.$route.query);
      }
    );
    await this.from_route(this.$route.params, this.$route.query);
  },

  methods: {
    async from_route(params, query) {
      const regex = (query.regex || "false") == "true";
      const pattern = params.record_glob;
      const selected_records = params.selected_records;

      this.search_mode = regex ? "Regex" : "Glob";
      this.input_record_glob = pattern || (regex ? ".*" : "*");

      // Get all the record info we need in the background
      let table_selection = [];
      for (const rec of (selected_records || "").split("|")) {
        if (rec.length > 0) {
          this.$store.dispatch("get_record_info", { record_name: rec });
          table_selection.push({ pv: rec });
        }
      }

      if ((selected_records?.length ?? 0) > 0) {
        document.title = `WhatRecord? ${selected_records}`;
      } else {
        document.title = "WhatRecord?";
      }

      await this.$store.dispatch("find_record_matches", {
        pattern: pattern,
        max_pvs: this.max_pvs,
        regex: regex,
      });
      // Only after we have populated the table, set the selection
      this.table_selection = table_selection;
    },

    do_search() {
      this.$router.push({
        params: {
          record_glob: this.input_record_glob,
          selected_records: this.table_selection_list.join("|"),
        },
        query: {
          regex: this.regex,
        },
      });
    },

    on_table_selection() {
      this.do_search();
    },
  },
};
</script>

<style scoped>
.p-grid .search {
  padding: 1em;
}

.p-grid .option {
  padding: 1em;
}

.input_search {
  width: 100%;
}
</style>
