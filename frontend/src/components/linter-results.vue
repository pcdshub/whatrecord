<template>
  <div class="error-block" v-if="errors?.length > 0 || warnings?.length > 0">
    <template v-for="(error, idx) in errors" class="error-block" :key="idx">
      <script-context-link :context="error.context" :short="1" />
      [{{ error.name }}] error: {{ error.message }}<br />
    </template>
    <template v-for="(warning, idx) in warnings" class="error-block" :key="idx">
      <script-context-link :context="warning.context" :short="1" />
      [{{ warning.name }}] warning: {{ warning.message }}<br />
    </template>
  </div>
</template>

<script>
import DictionaryTable from "@/components/dictionary-table.vue";
import ScriptContextLink from "@/components/script-context-link.vue";

export default {
  name: "LinterResults",
  components: [DictionaryTable, ScriptContextLink],
  props: ["errors", "warnings"],
  beforeCreate() {
    // TODO: I don't think these are circular; why am I running into this?
    this.$options.components.DictionaryTable = DictionaryTable;
    this.$options.components.ScriptContextLink = ScriptContextLink;
  },
};
</script>

<style scoped></style>
