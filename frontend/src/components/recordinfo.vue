<template>
  <h3> {{ whatrec.name }} </h3>
  <!-- Available in {{ available_protocols }} -->
  <template v-for="(instance, idx) in [instance_v3, instance_pva]" :key="idx">
    <template v-if="instance != null">
      <script-context-link :context="instance.context" :short=false></script-context-link>
      <br/>
      <epics-format-record
        :name=instance.name
        :context=instance.context
        :fields=instance.fields
        :record_type=instance.record_type
        :is_grecord=instance.is_grecord
        :is_pva=instance.is_pva
      />

      <template v-for="plugin_name in plugins" :key="plugin_name">
        <template v-for="plugin_match in instance.metadata[plugin_name] || []" :key="plugin_match.name">
          <details>
            <summary>
              {{ plugin_name }} - {{ plugin_match.name }}
              <router-link :to="`/${plugin_name}/${plugin_match.name}`">
                (Details)
              </router-link>
            </summary>
            <dictionary-table
              :dict="plugin_match"
              :cls="'metadata'"
              :skip_keys="[]"
              />
          </details>
          <br />
        </template>
      </template>
    </template>

  </template>

  <Accordion :multiple="true">
    <AccordionTab :header="`Part of ${whatrec.ioc.name}`">
      <dictionary-table
        :dict="whatrec.ioc"
        :cls="'metadata'"
        :skip_keys="['commands', 'variables']">
      </dictionary-table>
    </AccordionTab>
    <AccordionTab header="Record links">
      <a :href="graph_link" target="_blank">
        <img class="svg-graph" :src="graph_link" />
      </a>
    </AccordionTab>
    <AccordionTab header="Archiver" :disabled="instance_v3 == null">
      <template v-if="instance_v3 != null">
        <a :href="appliance_viewer_url + instance_v3.name" target="_blank">
            <div v-if="instance_v3.metadata.archived">
                In archiver
            </div>
            <div v-else>
                Not in archiver
            </div>
        </a>
        <iframe
          :src="appliance_viewer_url + instance_v3.name"
          title="Archive viewer"
          v-if="instance_v3.metadata.archived"
          />
        </template>
    </AccordionTab>
    <AccordionTab header="Inter-IOC Links">
      <a :href="script_graph_link" target="_blank">
        <img class="svg-graph" :src="script_graph_link" />
      </a>
    </AccordionTab>
    <AccordionTab header="Gateway" :disabled="instance_v3 == null">
      <template v-if="instance_v3 != null && instance_v3.metadata.gateway != null && instance_v3.metadata.gateway.matches">
        <gateway-matches :matches="instance_v3.metadata.gateway.matches"/>
      </template>
    </AccordionTab>
    <AccordionTab header="Asyn" :disabled="whatrec.asyn_ports.length == 0">
      <asyn-port
        v-for:="(asyn_port, idx) in whatrec.asyn_ports"
        :asyn_port="asyn_port"
        :key="asyn_port.name"/>
    </AccordionTab>
    <AccordionTab header="Field table">
      <template v-if="instance_v3 != null">
        <b v-if="instance_pva != null">Channel Access (V3)</b>
        <record-field-table :fields="instance_v3.fields" :pva="false" />
      </template>
      <template v-if="instance_pva != null">
        <b v-if="instance_v3 != null">PVAccess</b>
        <record-field-table :fields="instance_pva.fields" :pva="true" />
      </template>
    </AccordionTab>
    <AccordionTab header="Raw information">
      <pre>{{whatrec}}</pre>
    </AccordionTab>
  </Accordion>
</template>

<script>
import AsynPort from './asyn-port.vue'
import DictionaryTable from './dictionary-table.vue'
import EpicsFormatRecord from './epics-format-record.vue'
import GatewayMatches from './gateway-matches.vue'
import RecordFieldTable from './record-field-table.vue'
import ScriptContextLink from './script-context-link.vue'
import Accordion from 'primevue/accordion';
import AccordionTab from 'primevue/accordiontab';

import { plugins } from '../settings.js';


export default {
  name: 'Recordinfo',
  props: {
    whatrec: Object,
    appliance_viewer_url: String
  },
  components: {
    AsynPort,
    DictionaryTable,
    EpicsFormatRecord,
    GatewayMatches,
    RecordFieldTable,
    ScriptContextLink,
    Accordion,
    AccordionTab,
  },
  computed: {
    graph_link() {
      return "/api/pv/" + this.whatrec.name + "/graph/svg";
    },
    script_graph_link() {
      return "/api/pv/" + this.whatrec.name + "/script-graph/svg";
    },
    available_protocols() {
      let protocols = [];
      if (this.instance_v3 != null) {
        protocols.push("Channel Access (CA)");
      }
      if (this.instance_pva != null) {
        protocols.push("PVAccess");
      }
      return protocols.join(", ");
    },
    instance_pva() {
      for (const instance of this.whatrec.instances) {
        if (instance.is_pva === true) {
          return instance;
        }
      }
      return null;
    },
    instance_v3() {
      for (const instance of this.whatrec.instances) {
        if (instance.is_pva === false) {
          return instance;
        }
      }
      return null;
    },
    happi_metadata() {
      if (this.instance_v3 == null) {
        return [];
      }
      return this.instance_v3.metadata["happi"] || [];
    },
    plugins() {
      return plugins;
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

iframe {
  min-height: 450px;
  width: 100%;
}
</style>
