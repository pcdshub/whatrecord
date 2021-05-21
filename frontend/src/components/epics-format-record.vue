<template>
  <div class="code">
    <template v-if="is_grecord">g</template>
    record({{ record_type }}, "{{ name }}") {<br/>
    <span
      class="recordfield"
      v-for="field in fields"
      :key=field.name
      :title="field.dtype + ':' + field.context.join(', ')"
      >
    &nbsp;field({{ field.name }}, "{{ field.value }}")   #  {{ field.dtype }}<br/>
    </span>
  }
  </div>
</template>

<script>
export default {
  name: 'EpicsFormatRecord',
  props: {
    name: String,
    context: Array,
    fields: Object,
    record_type: String,
    is_grecord: Boolean
  }
}
</script>

<style scoped>
</style>
