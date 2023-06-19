<template>
  <div class="grid option">
    <div class="col-6">
      <SelectButton
        v-model="search_mode"
        :options="search_mode_options"
        @click="push_route"
      />
    </div>
  </div>
  <div class="grid search">
    <div class="col-10">
      <form @submit.prevent="push_route" v-on:keyup.enter="push_route">
        <InputText
          type="text"
          v-model.trim.lazy="user_pattern"
          placeholder="*PV Glob*"
          class="input_search"
        />
      </form>
    </div>
    <div class="col-2">
      <Button @click="push_route()" icon="pi pi-search" :loading="searching" />
    </div>
  </div>
  <DataTable
    :value="table_data"
    v-model:selection="user_table_selection"
    selectionMode="multiple"
    dataKey="pv"
    class="p-datatable-sm"
    @rowSelect="on_table_selection"
    @rowUnselect="on_table_selection"
  >
    <Column field="pv" :header="`Results`"> </Column>
  </DataTable>
</template>

<script lang="ts">
import { use_configured_store } from "../stores";

import Button from "primevue/button";
import Column from "primevue/column";
import SelectButton from "primevue/selectbutton";
import DataTable from "primevue/datatable";
import InputText from "primevue/inputtext";
import { nextTick } from "vue";

interface TableData {
  pv: string;
}

export default {
  name: "Searchbar",
  components: {
    Button,
    Column,
    DataTable,
    SelectButton,
    InputText,
  },
  props: {
    pattern: {
      type: String,
      required: true,
    },
    use_regex: {
      type: Boolean,
      default: false,
    },
    record: {
      type: Array<string>,
      required: true,
    },
  },
  setup() {
    const store = use_configured_store();
    return { store };
  },
  data() {
    return {
      max_pvs: 200,
      user_table_selection: [] as TableData[],
      user_pattern: "*",
      search_mode: "Glob",
      last_query: {},
      search_mode_options: ["Glob", "Regex"],
    };
  },
  computed: {
    user_regex(): boolean {
      return this.search_mode === "Regex";
    },
    user_table_selection_list(): string[] {
      let as_list: string[] = [];
      Object.values(this.user_table_selection).forEach((d) =>
        as_list.push(d.pv),
      );
      return as_list;
    },

    searching() {
      return this.store.query_in_progress;
    },
    table_data(): TableData[] {
      const pattern_to_pvs = this.user_regex
        ? this.store.regex_to_pvs
        : this.store.glob_to_pvs;
      if (this.pattern in pattern_to_pvs) {
        const pvs = pattern_to_pvs[this.pattern];
        return pvs.map((value) => ({ pv: value }));
      }
      return [];
    },
  },

  emits: [],

  async mounted() {
    this.user_pattern = this.pattern;
    this.search_mode = this.use_regex ? "Regex" : "Glob";
    this.update_table_selection(this.record);
    await this.update_store();
  },

  async updated() {
    await this.update_store();
  },

  watch: {
    async $route() {
      // Wait until the prop is updated, then update the table DOM:
      await nextTick();
      this.update_table_selection(this.record);
    },
  },

  methods: {
    update_table_selection(records: string[]) {
      if (records == this.user_table_selection_list) {
        return;
      }
      let table_selection = [];
      for (const rec of records) {
        if (rec.length > 0) {
          table_selection.push({ pv: rec });
        }
      }
      this.user_table_selection = table_selection;
    },

    async update_store() {
      await this.update_record_search(this.user_pattern, this.user_regex);
      await this.update_selected_record_store();
    },

    async update_selected_record_store() {
      const record = this.record ?? "";
      document.title = `whatrecord? ${record}`;

      for (const rec of this.record) {
        if (rec.length > 0) {
          await this.store.get_record_info({ record_name: rec });
        }
      }
    },
    async update_record_search(pattern: string, regex: boolean) {
      this.search_mode = regex ? "Regex" : "Glob";
      // this.user_pattern = pattern || (regex ? ".*" : "*");
      await this.store.find_record_matches({
        pattern: pattern,
        max_pvs: this.max_pvs,
        regex: regex,
      });
    },
    push_route() {
      const query = {
        pattern: this.user_pattern,
        record: this.user_table_selection_list,
        regex: this.user_regex.toString(),
      };

      if (query != this.last_query) {
        this.$router.push({
          query: query,
        });
        this.last_query = query;
      }
    },

    on_table_selection() {
      this.push_route();
    },
  },
};
</script>

<style scoped>
.grid .search {
  padding: 1em;
}

.grid .option {
  padding: 1em;
}

.input_search {
  width: 100%;
}
</style>
