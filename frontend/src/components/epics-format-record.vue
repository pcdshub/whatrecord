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
      <template v-for="field in fields" :key="field.name">
        <epics-format-field
          :field="field"
          :field_info="record_defn?.fields[field.name] ?? null"
          :menus="menus"
          :autosave="autosave_fields[field.name]"
        />
      </template>
      <template v-for="field in new_autosave_fields" :key="field.name">
        <epics-format-field
          :field="field"
          :field_info="record_defn?.fields[field.name] ?? null"
          :menus="menus"
          :autosave="field"
        />
      </template>
      <!-- info nodes -->
      <span v-for="[key, value] in Object.entries(info_nodes)" :key="key">
        &nbsp;info({{ key }}, "{{ value }}")<br />
      </span>
      }
    </div>
  </template>
  <template v-else>
    <div class="code">
      "{{ name }}":<br />
      <span
        class="recordfield"
        v-for="field in fields"
        :key="field.name"
        :title="field.dtype + ':' + field.context.join(', ')"
      >
        &nbsp;
        <script-context-one-link
          :name="field.context[0][0]"
          :line="field.context[0][1]"
          :link_text="field.name"
          class="unassuming_link"
        />
        from from "{{ field.record_name }}.{{ field.field_name }}"
        <template v-if="Object.keys(field.metadata).length > 0"
          ># {{ field.metadata }}</template
        >
        <br />
      </span>
    </div>
  </template>
</template>

<script>
import EpicsFormatField from "./epics-format-field.vue";
import ScriptContextOneLink from "./script-context-one-link.vue";

export default {
  name: "EpicsFormatRecord",
  props: {
    context: Array,
    aliases: Array,
    fields: Object,
    is_grecord: Boolean,
    is_pva: Boolean,
    metadata: Object,
    info_nodes: Object,
    name: String,
    record_type: String,
    record_type_info: Object,
    record_defn: Object,
    menus: Object,
  },
  components: {
    EpicsFormatField,
    ScriptContextOneLink,
  },
  computed: {
    db_defined_fields() {
      // database-defined fields
      return Object.keys(this.fields);
    },

    new_autosave_fields() {
      // autosave fields without database defaults
      const new_field_names = Object.keys(this.autosave_fields).filter(
        field_name => this.db_defined_fields.indexOf(field_name) < 0
      );
      return new_field_names.map(
        field_name => this.autosave_fields[field_name]
      );
    },

    autosave_fields() {
      let fields = {};
      const record_defn = this.record_defn;

      function add_field(restore, field) {
        fields[field.field] = {
          name: field.field,
          context: field.context,
          value: field.value,
          dtype: record_defn?.fields[field.field]?.type,
        }
      }
      this.metadata?.autosave?.restore?.forEach(
        restore => Object.values(restore).forEach(
          field => add_field(restore, field)
        )
      );
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
