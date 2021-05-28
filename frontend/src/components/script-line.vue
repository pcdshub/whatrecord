<template>
  <tr>
    <td class="line-id">
      {{ line_id }}:
    </td>
    <td :class="script_line_class">
      <template v-if="result == null && error == null">
        <span class="script-line" :id="line_id">
          {{ line }}
        </span>
        <br/>
      </template>
      <template v-else>
        <details :id="line_id" class="script-line">
          <summary class="script-line">
            <span v-if="error != null" class="script-error-line">
              {{line}}
            </span>
            <span v-else-if="is_error_line" class="script-error-line">
              {{line}}
            </span>
            <span v-else class="script-line">{{line}}</span>
          </summary>

          <template v-if="result != null && result.hasOwnProperty('load_count')">
            <LinterResults
              :load_count="result.load_count"
              :errors="result.errors"
              :warnings="result.warnings"
              :macros="result.macros"
              />
          </template>
          <template v-else>
            <span v-if="error != null" class="error-block">
              <pre>{{error}}</pre>
            </span>
            <span v-if="result != null" class="result-block">
              <pre>{{ result }}</pre>
            </span>
          </template>
        </details>
      </template>
    </td>
  </tr>
</template>

<script>
import LinterResults from './linter-results.vue';

export default {
  name: 'ScriptLine',
  components: [
    LinterResults,
  ],
  props: ["context", "line", "outputs", "argv", "error", "redirects", "result"],
  computed: {
    line_id() {
      return this.context.map(ctx => ctx[1]).join(':');
    },
    script_line_class() {
      return (this.line == this.$route.params.line ? ["script-line-selected", "script-line"] : "script-line");
    },
    is_error_line() {
      return (
        this.result instanceof Object &&
        "load_count" in this.result &&
        (this.result.errors.length > 0 || this.result.warnings.length > 0)
      );
    },
    is_linter_results() {
      return (
        this.result instanceof Object &&
        "load_count" in this.result
      );
    },
  },
  beforeCreate() {
    // TODO: I don't think this is circular; why am I running into this?
    // V2 ref: https://vuejs.org/v2/guide/components-edge-cases.html#Circular-References-Between-Components
    this.$options.components.LinterResults = require('./linter-results.vue').default;
  },
}
</script>

<style scoped>
td {
  vertical-align: top;
  text-align: left;
}

td.line-id {
  font-family: monospace;
  user-select: none;
}

td.script-line {
  font-family: monospace;
}

td.script-line-selected {
  font-family: monospace;
  background: lightyellow;
}

details > summary {
    list-style-type: none;
}

details > summary::marker {
    display: none;
}

details.script-line > summary::before {
    content: '';
}

.script-error-line {
  color: red;
}

</style>
