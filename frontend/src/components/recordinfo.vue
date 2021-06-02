<template>
  <script-context-link :context="record_info.instance.context" :short=false></script-context-link>

  <Accordion :multiple="true" :activeIndex="[0, 1, 2]">
    <AccordionTab header="Record">
      <a :href="graph_link" target="_blank">
        <img class="svg-graph" :src="graph_link" />
      </a>
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
      />
    </AccordionTab>
    <AccordionTab header="Inter-IOC Links">
      <a :href="script_graph_link" target="_blank">
        <img class="svg-graph" :src="script_graph_link" />
      </a>
    </AccordionTab>
    <AccordionTab header="Gateway">
      <template v-if="record_info.instance.metadata.gateway.matches">
        <gateway-matches :matches="record_info.instance.metadata.gateway.matches"/>
      </template>
    </AccordionTab>
    <AccordionTab header="Asyn" :disabled="record_info.asyn_ports.length == 0">
      <asyn-port
        v-for:="(asyn_port, idx) in record_info.asyn_ports"
        :asyn_port="asyn_port"
        :key="asyn_port.name"/>
    </AccordionTab>
    <AccordionTab header="Field table">
      <record-field-table
        :fields=record_info.instance.fields
      />
    </AccordionTab>
    <AccordionTab header="Raw information">
      <pre>{{record_info}}</pre>
    </AccordionTab>
  </Accordion>
</template>

<script>
import AsynPort from './asyn-port.vue'
import EpicsFormatRecord from './epics-format-record.vue'
import GatewayMatches from './gateway-matches.vue'
import RecordFieldTable from './record-field-table.vue'
import ScriptContextLink from './script-context-link.vue'
import Accordion from 'primevue/accordion';
import AccordionTab from 'primevue/accordiontab';


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
    Accordion,
    AccordionTab,
  },
  computed: {
    graph_link() {
      return "/api/pv/" + this.record_info.instance.name + "/graph/svg";
    },
    script_graph_link() {
      return "/api/pv/" + this.record_info.instance.name + "/script-graph/svg";
    }
  }
}
</script>

<style scoped>
.svg-graph {
  max-width: 70%;
}

.p-panel {
  padding-bottom: 1em;
}
</style>
