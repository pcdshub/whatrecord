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
          <script-context-link :context="match.context" :short="true" />
        </td>
        <td>{{ match.expression }}</td>
        <td>{{ match.details.join(" ") }}</td>
        <td>
          <!--
          <template v-if="match.comment_context">
            <script-context-link :context="match.comment_context" :short="true" />
          </template>
          -->
          {{ match.comment }}
        </td>
      </tr>
    </tbody>
  </table>
</template>

<script>
import ScriptContextLink from './script-context-link.vue'

export default {
  name: 'GatewayMatches',
  props: {
    matches: Object
  },
  components: {
    ScriptContextLink,
  },
}
</script>

<style scoped>
table {
    width: 100%;
}

td {
    font-family: monospace;
}
</style>
