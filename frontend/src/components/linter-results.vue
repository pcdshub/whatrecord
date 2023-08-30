<template>
  <div
    class="error-block"
    v-if="(errors && errors?.length > 0) || (warnings && warnings?.length > 0)"
  >
    <template
      v-for="(error, _idx) in errors || []"
      class="error-block"
      :key="_idx"
    >
      <script-context-link :context="error.context" :short="1" />
      [{{ error.name }}] error: {{ error.message }}<br />
    </template>
    <template
      v-for="(warning, _idx) in warnings || []"
      class="error-block"
      :key="_idx"
    >
      <script-context-link :context="warning.context" :short="1" />
      [{{ warning.name }}] warning: {{ warning.message }}<br />
    </template>
  </div>
</template>

<script lang="ts">
import { PropType } from "vue";
import DictionaryTable from "./dictionary-table.vue";
import ScriptContextLink from "./script-context-link.vue";
import { LinterMessage } from "@/types";

export default {
  name: "LinterResults",
  components: { DictionaryTable, ScriptContextLink },
  props: {
    errors: {
      type: Array as PropType<LinterMessage[] | null>,
      required: true,
    },
    warnings: {
      type: Array as PropType<LinterMessage[] | null>,
      required: true,
    },
  },
};
</script>

<style scoped></style>
