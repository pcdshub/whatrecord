<template>
  <div class="context">
    <template v-for="[name, line] in context" :key="name + line">
      {{ prefix }}
      <script-context-one-link :name="name" :line="line" :short="short" />
      <br />
    </template>
  </div>
</template>

<script lang="ts">
import { PropType } from "vue";
import ScriptContextOneLink from "./script-context-one-link.vue";
import { FullLoadContext } from "../types";

export default {
  name: "ScriptContextLink",
  props: {
    context: Array as PropType<FullLoadContext>,
    short: {
      type: Number,
      default: 0,
    },
    prefix: {
      type: String,
      default: ">",
    },
  },
  components: {
    ScriptContextOneLink,
  },
};
</script>

<style scoped></style>
