<template>
  <tr>
    <td :class="line_id_class">
      {{ line_id }}:
    </td>
    <td :class="script_line_class">
      <template v-if="!has_details">
        <pre class="script-line" :id="line_id">{{ line.line.replace("\t", "    ") }}</pre>
      </template>
      <template v-else>
        <details :id="line_id" class="script-line">
          <summary class="script-line">
            <span :class='is_error_line ? "script-error-line" : "script-line"'>
              {{line.line}}
            </span>
          </summary>

          <template v-if="is_linter_results">
            <LinterResults
              :load_count="line.result.load_count"
              :errors="line.result.errors"
              :warnings="line.result.warnings"
              :macros="line.result.macros"
              />
          </template>
          <template v-else>
            <span v-if="line.error != null" class="error-block">
              <template v-if="typeof line.error == 'string'">
                <pre>{{ line.error }}</pre>
              </template>
              <template v-else>
                <dictionary-table
                  :dict="line.error"
                  cls="error"
                  :skip_keys="[]" />
              </template>
            </span>
            <span v-if="line.result != null" class="result-block">
              <template v-if="typeof line.result == 'string'">
                <pre>{{ line.result }}</pre>
              </template>
              <template v-else>
                <dictionary-table
                  :dict="line.result"
                  cls="result"
                  :skip_keys="[]"
                />
              </template>
            </span>
          </template>
          <template v-if="command_info_table != null">
            <br />
            <dictionary-table
              :dict="command_info_table"
              key_column="Argument"
              value_column="Value"
              cls="command_info_table"
              :skip_keys="[]" />
          </template>

        </details>
      </template>
    </td>
  </tr>
</template>

<script>
import DictionaryTable from './dictionary-table.vue';
import LinterResults from './linter-results.vue';

export default {
  name: 'ScriptLine',
  components: [
    DictionaryTable,
    LinterResults,
  ],
  props: [
    "line",
    "all_commands"
  ],
  computed: {
    command() {
      if (this.line.argv != null && this.line.argv.length > 0) {
        return this.line.argv[0];
      }
      return null;
    },

    command_info() {
      const command = this.command;
      if (command && command in this.all_commands) {
        return this.all_commands[command];
      }
      return null;
    },

    command_info_table() {
      if (this.command_info == null || this.command_info.length == 0) {
        return null;
      }
      var info_table = {};
      if (this.command_info["usage"]) {
        info_table["usage"] = this.command_info["usage"];
      }
      for (const [idx, arg_info] of this.command_info["args"].entries()) {
        const argv_idx = idx + 1;
        const arg_value = argv_idx < this.argv.length ? this.argv[argv_idx] : "";
        info_table[arg_info.name] = arg_value;
      }
      return info_table;
    },

    line_id() {
      return this.line.context.map(ctx => ctx[1]).join(':');
    },

    line_id_class() {
      let classes = ["line-id"];
      if (this.is_error_line) {
        classes.push("line-id-error");
      }
      if (this.has_details) {
        classes.push("line-id-details");
      }
      return classes;
    },

    has_details() {
      return !(this.line.result == null && this.line.error == null && this.command_info == null);
    },

    is_error_line() {
      return (this.is_db_load_error || this.line.error != null);
    },

    script_line_class() {
      if (this.line.context.length > 0 && this.line.context[0][1] == this.$route.params.line) {
        return ["script-line-selected", "script-line"];
      }
      return "script-line";
    },

    is_db_load_error() {
      return (
        this.line.result instanceof Object &&
        "load_count" in this.line.result &&
        (this.line.result.errors.length > 0 || this.line.result.warnings.length > 0)
      );
    },

    is_linter_results() {
      return (
        this.line.result instanceof Object &&
        "load_count" in this.line.result
      );
    },
  },
  beforeCreate() {
    // TODO: I don't think this is circular; why am I running into this?
    // V2 ref: https://vuejs.org/v2/guide/components-edge-cases.html#Circular-References-Between-Components
    this.$options.components.LinterResults = require('./linter-results.vue').default;
    this.$options.components.DictionaryTable = require('./dictionary-table.vue').default;
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
  width: 0;
}

td.line-id-details {
  font-weight: bold;
}

td.line-id-error {
  font-weight: bold;
  color: red;
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

.error-block {
  background: lightred;
  border: 1px solid lightgray;
  border-left: 3px solid lightcoral;
  color: black;
  page-break-inside: avoid;
  font-family: monospace;
  font-size: 15px;
  line-height: 1.0;
  margin-bottom: 0.5em;
  max-width: 100%;
  overflow: auto;
  padding: 15px;
  display: block;
  word-wrap: break-word;
}

.result-block {
  border-left: 3px solid lightgray;
  color: black;
  page-break-inside: avoid;
  font-family: monospace;
  font-size: 15px;
  line-height: 1.0;
  margin-bottom: 0.5em;
  max-width: 100%;
  overflow: auto;
  padding: 15px;
  display: block;
  word-wrap: break-word;
}

pre {
  margin: 0em;
}
</style>
