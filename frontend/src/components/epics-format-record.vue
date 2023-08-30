<template>
  <template v-if="!is_pva">
    <div class="code">
      <template v-if="is_grecord">g</template>
      record({{ record_type }}, "{{ name }}") {<br />
      <!-- aliases -->
      <span v-for="alias in aliases" :key="alias">
        &nbsp;alias("{{ alias }}")<br />
      </span>
      <!-- fields -->
      <template v-for="field in v3_fields" :key="field.name">
        <epics-format-field
          :field="field"
          :field_info="record_defn?.fields[field.name] ?? null"
          :menus="menus"
          :autosave="autosave_fields[field.name]?.value ?? null"
        />
      </template>
      <template v-for="field in new_autosave_fields" :key="field.name">
        <epics-format-field
          :field="field"
          :field_info="record_defn?.fields[field.name] ?? null"
          :menus="menus"
          :autosave_value="field.value"
        />
      </template>
      <!-- info nodes -->
      <span v-for="node in info_node_list" :key="node.key">
        &nbsp;info({{ node.key }}, "{{ node.value }}")<br />
      </span>
      }
    </div>

    <span v-for="pvagroup in Object.keys(q_group)" :key="pvagroup">
      &gt;
      <router-link
        :to="{
          name: 'whatrec',
          query: { pattern: pvagroup, record: pvagroup, use_regex: 'false' },
        }"
      >
        {{ pvagroup }}
      </router-link>
      <br />
      <br />
    </span>
  </template>
  <template v-else>
    <div class="code">
      "{{ name }}":<br />
      <span
        class="recordfield"
        v-for="field in pva_fields"
        :key="field.name"
        :title="field.context.join(', ')"
      >
        &nbsp; .<script-context-one-link
          :name="field.context[0][0]"
          :line="field.context[0][1]"
          :link_text="field.name || 'unknown'"
          class="unassuming_link"
        />
        =
        <router-link
          :to="{
            name: 'whatrec',
            query: {
              pattern: field.record_name,
              record: field.record_name,
              use_regex: 'false',
            },
          }"
          :title="JSON.stringify(field.metadata, null, 2)"
        >
          {{ field.record_name }}.{{ field.field_name }}
        </router-link>
        <br />
      </span>
    </div>
  </template>
</template>

<script lang="ts">
import type { PropType } from "vue";

import EpicsFormatField from "./epics-format-field.vue";
import ScriptContextOneLink from "./script-context-one-link.vue";
import {
  AutosaveMetadataAnnotation,
  AutosaveRestoreValue,
  RecordField,
  DatabaseMenu,
  AnyField,
  FullLoadContext,
  RecordType,
  PVAFieldReference,
} from "../types";

interface AutosaveDisplayField {
  name: string;
  context: FullLoadContext;
  value: Object;
  dtype: string;
}

interface InfoNodePair {
  key: string;
  value: object;
}

export default {
  name: "EpicsFormatRecord",
  props: {
    context: {
      type: Object as PropType<FullLoadContext>,
      required: true,
    },
    aliases: {
      type: Array as PropType<string[]>,
      required: false,
      default: [],
    },
    fields: {
      type: Object as PropType<Record<string, AnyField>>,
      required: true,
    },
    is_grecord: {
      type: Boolean,
      required: false,
      default: false,
    },
    is_pva: {
      type: Boolean,
      required: true,
    },
    metadata: {
      type: Object as PropType<Record<string, object>>,
      required: true,
    },
    info_nodes: {
      type: Object as PropType<Record<string, object>>,
      required: true,
    },
    name: {
      type: String,
      required: true,
    },
    record_type: {
      type: String,
      required: true,
    },
    record_defn: {
      type: Object as PropType<RecordType | null>,
      required: false,
    },
    menus: Object as PropType<Record<string, DatabaseMenu> | null>,
  },
  components: {
    EpicsFormatField,
    ScriptContextOneLink,
  },
  computed: {
    v3_fields(): RecordField[] {
      let fields: AnyField[] = Object.values(this.fields);
      // We know there are no PVA field references here:
      return fields as RecordField[];
    },
    pva_fields(): PVAFieldReference[] {
      let fields: AnyField[] = Object.values(this.fields);
      // We know there are no V3 field references here:
      return fields as PVAFieldReference[];
    },
    field_names_in_database(): string[] {
      // database-defined fields
      return Object.keys(this.fields);
    },

    info_node_list(): InfoNodePair[] {
      let pairs = [];
      for (const key of Object.keys(this.info_nodes)) {
        pairs.push({ key: key, value: this.info_nodes[key] });
      }
      return pairs;
    },
    new_autosave_fields() {
      // autosave fields without database defaults
      const new_field_names = Object.keys(this.autosave_fields).filter(
        (field_name) => this.field_names_in_database.indexOf(field_name) < 0,
      );
      return new_field_names.map(
        (field_name) => this.autosave_fields[field_name],
      );
    },

    q_group() {
      const info_nodes = this.info_nodes;
      if (!info_nodes) {
        return {};
      }
      if ("Q:group" in info_nodes) {
        return info_nodes["Q:group"];
      }
      return {};
    },

    autosave_fields(): Record<string, AutosaveDisplayField> {
      let fields: Record<string, AutosaveDisplayField> = {};
      const record_defn = this.record_defn;

      function add_field(field: AutosaveRestoreValue) {
        fields[field.field] = {
          name: field.field,
          context: field.context,
          value: field.value,
          dtype: record_defn?.fields[field.field]?.type ?? "",
        };
      }
      const autosave: AutosaveMetadataAnnotation =
        this.metadata?.autosave ?? null;
      if (autosave !== null) {
        autosave.restore?.forEach((restore) =>
          Object.values(restore).forEach((field) => add_field(field)),
        );
      }
      return fields;
    },
  },
};
</script>

<style scoped>
.code {
  background: #efefef;
  border-left: 3px solid lightgreen;
  color: black;
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
.unassuming_link {
  color: black;
  text-decoration: none;
}
</style>
