<template>
  <h3>{{ whatrec.name }}</h3>
  <!-- Available in {{ available_protocols }} -->
  <template v-for="pair in displayed_records">
    <template v-if="pair.instance != null">
      <script-context-link
        :context="pair.instance.context"
        :short="0"
      ></script-context-link>
      <br />
      <epics-format-record
        :name="pair.instance.name"
        :aliases="pair.instance.aliases"
        :context="pair.instance.context"
        :fields="pair.instance.fields"
        :record_type="pair.instance.record_type"
        :is_grecord="pair.instance.is_grecord"
        :is_pva="pair.instance.is_pva"
        :info_nodes="pair.instance.info"
        :metadata="pair.instance.metadata"
        :record_defn="pair.definition"
        :menus="whatrec.menus"
      />

      <template
        v-for="[plugin, plugin_match] of Object.entries(pair.plugin_matches)"
        :key="plugin_match"
      >
        <template v-for="item of plugin_match">
          <details>
            <summary>
              {{ plugin }} - {{ item.name }}
              <router-link :to="{ name: plugin, query: { item: item.name } }">
                (Details)
              </router-link>
            </summary>
            <dictionary-table
              :dict="item"
              :cls="'metadata'"
              :skip_keys="['_whatrecord']"
            />
          </details>
        </template>
        <br />
      </template>
    </template>
  </template>

  <template v-if="streamdevice_metadata">
    <details>
      <summary>
        StreamDevice protocol (
        <span class="monospace">
          {{ streamdevice_metadata.protocol_file }} </span
        >,
        <span class="monospace">
          "{{ streamdevice_metadata.protocol_name }}"
        </span>
        )
      </summary>
      <dictionary-table
        :dict="streamdevice_metadata as any"
        :cls="'metadata'"
        :skip_keys="['protocol']"
      />
      <template v-if="'protocol' in streamdevice_metadata">
        <br />Protocol:
        <dictionary-table
          :dict="streamdevice_metadata.protocol"
          :cls="'metadata'"
          :skip_keys="['commands']"
        />
        <br />Commands:
        <br />
        <span class="code">
          <template
            v-for="command in streamdevice_commands"
            :key="command.name"
          >
            {{ command.name }} {{ command.arguments.join(" ") }}<br />
          </template>
        </span>
      </template>
    </details>
    <br />
  </template>

  <Accordion :multiple="true" class="accordion">
    <AccordionTab :header="`Part of ${whatrec.ioc?.name}`">
      <ioc-info :ioc_info="whatrec.ioc" v-if="whatrec.ioc" />
    </AccordionTab>
    <AccordionTab header="Record links" v-if="show_graph" ref="link_tab">
      <div id="graph_div" ref="graph_div">
        <GraphvizGraph
          :width="graph_width"
          :height="graph_height"
          :fit_graph="false"
          :save_filename="record?.name"
          :dot_source="pv_graph_dot_source"
        />
      </div>
    </AccordionTab>
    <AccordionTab
      header="Archiver"
      v-if="record != null && appliance_viewer_url"
    >
      <template v-if="record != null && appliance_viewer_url">
        <a :href="appliance_viewer_url" target="_blank"> Archive Viewer </a>
        <iframe :src="appliance_viewer_url" title="Archive viewer" />
      </template>
    </AccordionTab>
    <AccordionTab header="Autosave" v-if="record && autosave != null">
      <template v-if="autosave.disconnected">
        Disconnected fields:
        <ul>
          <li v-for="field in autosave.disconnected" :key="field">
            {{ field }}
          </li>
        </ul>
      </template>
      <template v-for="(table, _idx) in autosave_restore_tables" :key="_idx">
        <DataTable :value="Object.values(table)" dataKey="name">
          <Column
            field="field"
            header="Field"
            :sortable="true"
            style="width: 10%"
          />
          <Column field="value" header="Value" :sortable="true" />
          <Column field="context" header="Context" :sortable="true">
            <template #body="{ data }">
              <script-context-link :context="data.context" :short="3" />
            </template>
          </Column>
        </DataTable>
      </template>
      <template v-if="autosave.error">
        Autosave errors on {{ whatrec.ioc?.name }}:
        <template v-for="error of autosave.error ?? []" :key="error">
          <pre>{{ error }}</pre>
        </template>
      </template>
    </AccordionTab>
    <AccordionTab header="Gateway" v-if="gateway_matches">
      <gateway-matches :matches="gateway_matches" />
    </AccordionTab>
    <AccordionTab header="Access Security Group" v-if="asg != null">
      <dictionary-table :dict="asg" :cls="'metadata'" :skip_keys="[]" />
    </AccordionTab>
    <AccordionTab header="Asyn" v-if="asyn">
      <asyn-port
        v-for:="asyn_port in asyn.ports"
        :asyn_port="asyn_port"
        :key="asyn_port.name"
      />
    </AccordionTab>
    <AccordionTab header="Field table">
      <template v-if="record != null">
        <b v-if="pva_group != null">Channel Access (V3)</b>
        <record-field-table :fields="record.fields" :pva="false" />
      </template>
      <template v-if="pva_group != null">
        <b v-if="record != null">PVAccess</b>
        <record-field-table :fields="pva_group.fields" :pva="true" />
      </template>
    </AccordionTab>
    <AccordionTab header="Raw information">
      <pre>{{ whatrec }}</pre>
    </AccordionTab>
  </Accordion>
</template>

<script lang="ts">
import type { PropType } from "vue";

import AsynPort from "./asyn-port.vue";
import DictionaryTable from "./dictionary-table.vue";
import EpicsFormatRecord from "./epics-format-record.vue";
import GatewayMatches from "./gateway-matches.vue";
import GraphvizGraph from "./graphviz-graph.vue";
import IocInfo from "./ioc-info.vue";
import RecordFieldTable from "./record-field-table.vue";
import ScriptContextLink from "./script-context-link.vue";

import Accordion from "primevue/accordion";
import AccordionTab from "primevue/accordiontab";
import Column from "primevue/column";
import DataTable from "primevue/datatable";

import { use_configured_store } from "@/stores";
import { Plugin, plugins } from "../settings";
import {
  RecordType,
  WhatRecord,
  GatewayMatch,
  GatewayMetadata,
  AutosaveMetadataAnnotation,
  RecordInstance,
} from "../types";

import { AsynMetadata } from "@/types/asyn";
import {
  Command as StreamDeviceCommand,
  StreamDeviceRecordAnnotation,
} from "@/types/stream";

interface PluginMatch {
  name: string;
  [x: string]: any;
}

interface DisplayedRecords {
  definition: RecordType | null;
  instance: RecordInstance;
  plugin_matches: Record<string, PluginMatch[]>;
}

function get_plugin_matches(
  metadata: Record<string, any>,
): Record<string, any> {
  // v-for="plugin_match in pair.instance.metadata[plugin.name] || {}"
  let result: Record<string, any> = {};
  for (const plugin of plugins) {
    if (plugin.name in metadata) {
      result[plugin.name] = metadata[plugin.name];
    }
  }
  return result;
}

export default {
  name: "Recordinfo",
  props: {
    whatrec: {
      type: Object as PropType<WhatRecord>,
      required: true,
    },
  },
  components: {
    AsynPort,
    Column,
    DataTable,
    DictionaryTable,
    EpicsFormatRecord,
    GatewayMatches,
    GraphvizGraph,
    IocInfo,
    RecordFieldTable,
    ScriptContextLink,
    Accordion,
    AccordionTab,
  },
  setup() {
    const store = use_configured_store();
    return { store };
  },
  data() {
    return {
      pv_graph_dot_source: "",
      graph_width: 300,
      graph_height: 300,
      show_graph: true,
    };
  },
  computed: {
    displayed_records(): DisplayedRecords[] {
      let result = [];
      if (this.record != null) {
        result.push({
          definition: this.record_defn,
          instance: this.record,
          plugin_matches: get_plugin_matches(this.record.metadata),
        });
        console.log("matches", result);
      }
      if (this.pva_group != null) {
        result.push({
          definition: null,
          instance: this.pva_group,
          plugin_matches: get_plugin_matches(this.pva_group.metadata),
        });
      }
      return result;
    },
    appliance_viewer_url() {
      const url: string = import.meta.env.WHATRECORD_ARCHIVER_URL || "";
      if (!url || !this.record) {
        return null;
      }
      return url + this.record.name;
    },
    available_protocols() {
      let protocols = [];
      if (this.record != null) {
        protocols.push("Channel Access (CA)");
      }
      if (this.pva_group != null) {
        protocols.push("PVAccess");
      }
      return protocols.join(", ");
    },
    pva_group() {
      return this.whatrec.pva_group;
    },
    record() {
      return this.whatrec.record ? this.whatrec.record.instance : null;
    },
    record_defn(): RecordType | null {
      if (this.whatrec.record == null) {
        return null;
      }
      return this.whatrec.record.definition ?? null;
    },
    asg() {
      return this.record?.metadata["asg"];
    },
    autosave(): AutosaveMetadataAnnotation | null {
      return (
        (this.record?.metadata["autosave"] as AutosaveMetadataAnnotation) ??
        null
      );
    },
    asyn(): AsynMetadata | null {
      return (this.record?.metadata["asyn"] as AsynMetadata) ?? null;
    },
    gateway_matches(): GatewayMatch[] | null {
      const gateway: GatewayMetadata | null =
        (this.record?.metadata["gateway"] as GatewayMetadata) ?? null;
      if (!gateway) {
        return null;
      }
      return gateway.matches;
    },
    autosave_restore_tables() {
      return this.autosave?.restore ?? [];
    },
    streamdevice_metadata(): StreamDeviceRecordAnnotation | null {
      // this shows I don't know what I'm doing with typescript except silencing
      // the linter:
      let result = this.record?.metadata?.streamdevice ?? null;
      return result ? (result as StreamDeviceRecordAnnotation) : null;
    },
    streamdevice_commands(): StreamDeviceCommand[] {
      return this.streamdevice_metadata?.protocol?.commands ?? [];
    },
    plugins(): Plugin[] {
      return plugins;
    },
  },

  async mounted() {
    await this.update_record_info();
  },

  async updated() {
    await this.update_record_info();
  },

  methods: {
    async update_record_info() {
      const graph = await this.store.get_record_link_graph({
        record_name: this.whatrec.name,
      });
      const graph_div = this.$refs.graph_div as HTMLDivElement | null;
      const link_tab = this.$refs.link_tab as HTMLElement | null;
      if (!graph_div || !link_tab) {
        console.error("What happened? No graph or tab?");
        this.pv_graph_dot_source = "digraph { unknown error }";
        this.show_graph = false;
        return;
      }
      this.graph_width = graph_div.clientWidth || window.innerWidth * 0.75;
      this.graph_height = graph_div.clientHeight || window.innerHeight * 0.25;
      this.pv_graph_dot_source = graph?.source ?? "";
      this.show_graph = this.pv_graph_dot_source.length > 0;
    },
  },
};
</script>

<style scoped>
#button-save-svg {
  max-width: 10%;
  max-height: 10%;
}

.monospace {
  font-family: monospace;
}

.p-panel {
  padding-bottom: 1em;
}

iframe {
  min-height: 450px;
  width: 100%;
}

.accordion {
  max-width: 76vw;
}

.code {
  background: var(--surface-f);
  border-left: 3px solid var(--surface-600);
  color: var(--text-color);
  display: block;
  font-family: monospace;
  font-size: 15px;
  line-height: 1;
  margin-bottom: 1.6em;
  max-width: 100%;
  overflow: auto;
  padding: 15px;
  page-break-inside: avoid;
  word-wrap: break-word;
}

#graph_div {
  height: 100%;
  width: 100%;
  min-width: 50%;
  min-height: 50%;
}
</style>
