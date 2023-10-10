<template>
  <table class="table" v-if="matches.length > 0">
    <thead>
      <tr>
        <th>File</th>
        <th>Expression</th>
        <th>Details</th>
        <th>Comment</th>
      </tr>
    </thead>
    <tbody>
      <tr v-for="(match, idx) in matches" :key="idx">
        <td>
          <script-context-link :context="match.rule.context" :short="2" />
        </td>
        <td>
          <router-link
            :to="{
              name: 'whatrec',
              query: {
                pattern: match.rule.pattern,
                record: [],
                regex: 'true',
              },
            }"
          >
            {{ match.rule.pattern }}
          </router-link>
        </td>
        <td>
          {{ match.rule.command }}
          <template v-if="match.rule.command == 'ALLOW'">
            {{ match.rule?.access ?? "(DEFAULT)" }}
          </template>
          <template v-else-if="match.rule.command == 'DENY'">
            Hosts: {{ match.rule.hosts?.join(" ") ?? "(All hosts)" }}
          </template>
          <template v-else-if="match.rule.command == 'ALIAS'">
            {{ match.rule?.access ?? "(DEFAULT)" }}
            {{ match.groups }}
          </template>
        </td>
        <td>
          <pre>{{ match.rule.header }}</pre>
        </td>
      </tr>
    </tbody>
  </table>
</template>

<script lang="ts">
import ScriptContextLink from "./script-context-link.vue";

export default {
  name: "GatewayMatches",
  props: {
    matches: {
      type: Object,
      required: true,
    },
  },
  components: {
    ScriptContextLink,
  },
};
</script>

<style scoped>
table {
  width: 100%;
}

td {
  font-family: monospace;
}
</style>
