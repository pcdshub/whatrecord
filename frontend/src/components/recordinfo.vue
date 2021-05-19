<template>
  <script-context-link :context="info.instance.context" :short=false></script-context-link>
  <a :href="appliance_viewer_url + info.instance.name" target="_blank">
      <div v-if="info.instance.metadata.archived">
          In archiver
      </div>
      <div v-else>
          Not in archiver
      </div>
  </a>
  <epics-format-record
    :name=info.instance.name
    :context=info.instance.context
    :fields=info.instance.fields
    :record_type=info.instance.record_type
    :is_grecord=info.instance.is_grecord
  ></epics-format-record>

  <a :href="'/api/pv/' + info.instance.name + '/graph/svg'" target="_blank">
    <img
      class="svg-graph"
      :src="'/api/pv/' + info.instance.name + '/graph/svg'" />
  </a>

  <details open=true class="title">
    <summary class="title">Gateway details</summary>
    <template v-if="info.instance.metadata.gateway.matches">
      <gateway-matches :matches="info.instance.metadata.gateway.matches">
      </gateway-matches>
    </template>
  </details>

  <details open=true class="title">
    <summary class="title">Asyn details</summary>
    <asyn-port
    v-for:="asyn_port in info.asyn_ports"
    :asyn_port="asyn_port"
    :key="asyn_port.name"></asyn-port>
  </details>

  <details open=true class="title">
  <summary class="title">Field table</summary>
  <record-field-table
    :fields=info.instance.fields
  ></record-field-table>
  </details>

  <details class="title">
  <summary class="title">Raw information</summary>
  <pre>{{info}}</pre>
  </details>
</template>

<script>
import AsynPort from './asyn-port.vue'
import EpicsFormatRecord from './epics-format-record.vue'
import GatewayMatches from './gateway-matches.vue'
import RecordFieldTable from './record-field-table.vue'
import ScriptContextLink from './script-context-link.vue'

export default {
  name: 'Recordinfo',
  props: {
    info: Object,
    appliance_viewer_url: String
  },
  components: {
    AsynPort,
    EpicsFormatRecord,
    GatewayMatches,
    RecordFieldTable,
    ScriptContextLink,
  },
}
</script>

<style scoped>
</style>
