<template>
  <DataTable class="p-datatable-sm" :value="Object.values(fields)">
    <Column field="name" header="Field" />
    <Column field="value" header="Value" v-if="!pva" />
    <Column field="dtype" header="Type" v-if="!pva" />
    <Column field="record_name" header="Record" v-if="pva" />
    <Column field="field_name" header="Field" v-if="pva" />
    <Column header="Context">
      <template #body="slotProps">
        <script-context-link :context="slotProps.data.context" :short="2" />
      </template>
    </Column>
  </DataTable>
</template>

<script lang="ts">
import ScriptContextLink from "./script-context-link.vue";
import Column from "primevue/column";
import DataTable from "primevue/datatable";
import { PropType } from "vue";

export default {
  name: "RecordFieldTable",
  props: {
    fields: {
      type: Object as PropType<Record<string, Object>>,
      required: true,
    },
    pva: Boolean,
  },
  components: {
    Column,
    DataTable,
    ScriptContextLink,
  },
};
</script>

<style scoped></style>
