<template>
  <table class="table" v-if="matches.length > 0">
    <thead>
      <tr>
        <th>File</th>
        <th>Expression</th>
        <th>Details</th>
      </tr>
    </thead>
    <tbody>
      <tr v-for="(match, idx) in matches" :key=idx>
        <td>
          <gateway-context-link :filename="match.filename" :lineno="match.lineno" />
        </td>
        <td>{{ match.expression }}</td>
        <td>{{match.details.join(" ")}}</td>
      </tr>
    </tbody>
  </table>
</template>

<script>
import GatewayContextLink from './gateway-context-link.vue'

export default {
  name: 'GatewayMatches',
  props: {
    matches: Object
  },
  components: {
    GatewayContextLink,
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
