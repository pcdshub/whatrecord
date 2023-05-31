<template>
  <h4>Asyn port: {{ asyn_port.name }}</h4>
  <dictionary-table
    :dict="asyn_port"
    :cls="'asyn_port'"
    :skip_keys="['motors']"
  >
  </dictionary-table>
  <template v-if="asyn_port.hasOwnProperty('motors')">
    <template v-for="(motor, motorname) in asyn_port.motors" :key="motorname">
      <h5>Motor port: {{ motorname }}</h5>
      <dictionary-table :dict="motor" :cls="'motor'" :skip_keys="[]">
      </dictionary-table>
    </template>
  </template>
</template>

<script>
import DictionaryTable from "@/components/dictionary-table.vue";

export default {
  name: "AsynPort",
  props: {
    asyn_port: Object,
  },
  components: [DictionaryTable],
  beforeCreate() {
    // TODO: I don't think this is circular; why am I running into this?
    // V2 ref: https://vuejs.org/v2/guide/components-edge-cases.html#Circular-References-Between-Components
    this.$options.components.DictionaryTable = DictionaryTable;
  },
};
</script>

<style scoped></style>
