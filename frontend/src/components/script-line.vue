<template>
  <tr>
    <td :class="line_id_class">{{ line_id }}:</td>
    <td :class="script_line_class">
      <template v-if="!has_details">
        <pre class="script-line" :id="line_id">{{
          line.line.replace("\t", "    ")
        }}</pre>
      </template>
      <template v-else>
        <details :id="line_id" class="script-line">
          <summary class="script-line">
            <span :class="is_error_line ? 'script-error-line' : 'script-line'">
              {{ line.line }}
            </span>
          </summary>

          <template v-if="command_info_table != null">
            <br />
            <dictionary-table
              :dict="command_info_table"
              key_column="Argument"
              value_column="Value"
              cls="command_info_table"
              :skip_keys="[]"
            />
          </template>

          <span v-if="line.error != null" class="error-block">
            <template v-if="typeof line.error == 'string'">
              <pre>{{ line.error }}</pre>
            </template>
            <template v-else>
              <dictionary-table
                :dict="line.error"
                cls="error"
                :skip_keys="[]"
              />
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
                :skip_keys="['arguments', 'lint']"
              />

              <linter-results
                :warnings="lint.warnings"
                :errors="lint.errors"
                cls="result"
                v-if="lint != null"
              />
            </template>
          </span>
        </details>
      </template>
    </td>
  </tr>
</template>

<script lang="ts">
import { PropType } from "vue";
import DictionaryTable from "./dictionary-table.vue";
import LinterResults from "./linter-results.vue";
import { DatabaseLint, IocshCommand, IocshResult } from "@/types";
import { IocshResultArgument } from "@/types";

interface TypicalResult {
  // whatrecord needs some uniformity here
  arguments?: IocshResultArgument[];
}

export default {
  name: "ScriptLine",
  components: { DictionaryTable, LinterResults },
  props: {
    line: {
      type: Object as PropType<IocshResult>,
      required: true,
    },
    all_commands: {
      type: Object as PropType<Record<string, IocshCommand>>,
      required: true,
    },
  },
  computed: {
    command(): string | null {
      if (this.line.argv != null && this.line.argv.length > 0) {
        return this.line.argv[0];
      }
      return null;
    },

    command_info(): IocshCommand | null {
      const command = this.command;
      if (command && command in this.all_commands) {
        return this.all_commands[command];
      }
      return null;
    },

    command_info_table() {
      if (!this.line || !this.line.argv) {
        return null;
      }

      let info_table: Record<string, any> = {};
      const result = this.line.result as TypicalResult;
      if (!this.command_info && result != null) {
        const args: IocshResultArgument[] = result.arguments ?? [];
        if (args.length > 0) {
          // whatrecord-suppplied argument information as a backup to
          // what gdb could more accurately provide
          args.forEach(
            (arg) => (info_table[`${arg.name} (${arg.type})`] = arg.value),
          );
          return info_table;
        }
        return null;
      }

      if (this.command_info != null) {
        if (this.command_info.usage) {
          info_table["usage"] = this.command_info.usage;
        }
        for (const [idx, arg_info] of this.command_info.args.entries()) {
          const argv_idx = idx + 1;
          const arg_value =
            argv_idx < this.line.argv.length ? this.line.argv[argv_idx] : "";
          info_table[arg_info.name] = arg_value;
        }
      }
      return info_table;
    },

    line_id() {
      return this.line.context.map((ctx) => ctx[1]).join(":");
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
      return !(
        this.line.result == null &&
        this.line.error == null &&
        this.command_info == null
      );
    },

    is_error_line() {
      return this.is_db_load_error || this.line.error != null;
    },

    script_line_class() {
      if (
        this.line.context.length > 0 &&
        this.line.context[0][1].toString() == this.$route.query.line
      ) {
        return ["script-line-selected", "script-line"];
      }
      return "script-line";
    },

    is_db_load_error() {
      const lint = this.lint;
      if (lint === null) {
        return false;
      }
      // Warnings/errors and 'load_count' from dbLoad:
      const result = this.line.result as Object;
      return "load_count" in result;
    },

    lint(): DatabaseLint | null {
      const result = this.line.result;
      if (
        result instanceof Object &&
        "warnings" in result &&
        "errors" in result
      ) {
        if (result.errors.length > 0 || result.warnings.length > 0) {
          return result as DatabaseLint;
        }
      }
      return null;
    },
  },
};
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
  content: "";
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
  line-height: 1;
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
  line-height: 1;
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
