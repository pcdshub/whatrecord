<template>
  <script-context-link :context="record_info.instance.context" :short=false></script-context-link>
  <a :href="appliance_viewer_url + record_info.instance.name" target="_blank">
      <div v-if="record_info.instance.metadata.archived">
          In archiver
      </div>
      <div v-else>
          Not in archiver
      </div>
  </a>
  <epics-format-record
    :name=record_info.instance.name
    :context=record_info.instance.context
    :fields=record_info.instance.fields
    :record_type=record_info.instance.record_type
    :is_grecord=record_info.instance.is_grecord
  ></epics-format-record>

  <a :href="'/api/pv/' + record_info.instance.name + '/graph/svg'" target="_blank">
    <img
      class="svg-graph"
      :src="'/api/pv/' + record_info.instance.name + '/graph/svg'" />
  </a>

  <details open=true class="title">
    <summary class="title">Gateway details</summary>
    <template v-if="record_info.instance.metadata.gateway.matches">
      <gateway-matches :matches="record_info.instance.metadata.gateway.matches">
      </gateway-matches>
    </template>
  </details>

  <details open=true class="title">
    <summary class="title">Asyn details</summary>
    <asyn-port
    v-for:="asyn_port in record_info.asyn_ports"
    :asyn_port="asyn_port"
    :key="asyn_port.name"></asyn-port>
  </details>

  <details open=true class="title">
  <summary class="title">Field table</summary>
  <record-field-table
    :fields=record_info.instance.fields
  ></record-field-table>
  </details>

  <details class="title">
  <summary class="title">Raw information</summary>
  <pre>{{record_info}}</pre>
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
    record_info: Object,
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
.svg-graph {
  max-width: 70%;
}

</style>
