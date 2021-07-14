<template>
  <template v-if="!is_pva">
    <div class="code">
      <template v-if="is_grecord">g</template>
      record({{ record_type }}, "{{ name }}") {<br/>
      <span
        class="recordfield"
        v-for="field in fields"
        :key=field.name
        :title="field.dtype + ':' + field.context.join(', ')"
        >
      &nbsp;field({{ field.name }}, "{{ field.value }}")<br/>
      </span>
    }
    </div>
  </template>
  <template v-else>
    <div class="code">
      "{{ name }}":<br/>
      <span
        class="recordfield"
        v-for="field in fields"
        :key=field.name
        :title="field.dtype + ':' + field.context.join(', ')"
        >
      &nbsp;"{{ field.name }}" from "{{ field.record_name }}.{{ field.field_name }}"
      <template v-if="Object.keys(field.metadata).length > 0">#  {{ field.metadata }}</template>
      <br/>
      </span>
    </div>
  </template>
</template>

<script>
export default {
  name: 'EpicsFormatRecord',
  props: {
    name: String,
    context: Array,
    fields: Object,
    record_type: String,
    is_grecord: Boolean,
    is_pva: Boolean,
  }
}
</script>

<style scoped>
.code {
  background: #efefef;
  border-left: 3px solid lightgreen;
  color: black;
  display: block;
  font-family: monospace;
  font-size: 15px;
  line-height: 1.0;
  margin-bottom: 1.6em;
  max-width: 100%;
  overflow: auto;
  padding: 15px;
  page-break-inside: avoid;
  word-wrap: break-word;
}
</style>
