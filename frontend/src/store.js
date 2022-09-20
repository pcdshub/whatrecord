import "es6-promise/auto";
import { createStore } from "vuex";

const axios = require("axios").default;

export const store = createStore({
  state: () => ({
    duplicates: {},
    file_info: {},
    gateway_info: null,
    glob_to_pvs: {},
    ioc_info: [],
    ioc_to_records: {},
    plugin_info: {},
    plugin_nested_info: {},
    pv_relations: {},
    queries_in_progress: 0,
    query_in_progress: false,
    record_info: {},
    regex_to_pvs: {},
  }),
  mutations: {
    start_query(state) {
      state.queries_in_progress += 1;
      state.query_in_progress = true;
    },
    end_query(state) {
      if (state.queries_in_progress > 0) {
        state.queries_in_progress -= 1;
      }
      if (state.queries_in_progress === 0) {
        state.query_in_progress = false;
      }
    },
    add_record_search_results(state, { pattern, pv_list, regex }) {
      if (regex) {
        state.regex_to_pvs[pattern] = pv_list;
      } else {
        state.glob_to_pvs[pattern] = pv_list;
      }
    },
    set_duplicates(state, { duplicates }) {
      state.duplicates = duplicates;
    },
    set_file_info(state, { filename, info }) {
      state.file_info[filename] = info;
    },
    set_ioc_info(state, { ioc_info }) {
      state.ioc_info = ioc_info;
    },
    set_gateway_info(state, { gateway_info }) {
      state.gateway_info = gateway_info;
    },
    set_plugin_info(state, { plugin_name, plugin_info }) {
      state.plugin_info[plugin_name] = plugin_info;
    },
    set_plugin_nested_keys(state, { plugin_name, keys }) {
      if (plugin_name in state.plugin_nested_info === false) {
        state.plugin_nested_info[plugin_name] = {
          keys: null,
          info: {},
        };
      }
      state.plugin_nested_info[plugin_name].keys = keys;
    },
    set_plugin_nested_info(state, { plugin_name, key, info }) {
      if (plugin_name in state.plugin_nested_info === false) {
        state.plugin_nested_info[plugin_name] = {
          keys: [],
          info: {},
        };
      }
      state.plugin_nested_info[plugin_name].info[key] = info;
    },
    add_record_info(state, { record, info }) {
      state.record_info[record] = info;
    },
    set_ioc_records(state, { ioc_name, records }) {
      state.ioc_to_records[ioc_name] = records;
    },
    set_pv_relations(state, { data }) {
      state.pv_relations = data;
    },
  },
  actions: {
    async update_ioc_info({ state, commit }) {
      if (state.ioc_info.length > 0) {
        return state.ioc_info;
      }
      try {
        await commit("start_query");
        const response = await axios.get("/api/ioc/matches", {
          params: { pattern: "*" },
        });
        await commit("set_ioc_info", { ioc_info: response.data.matches });
        return response.data.matches;
      } catch (error) {
        console.error(error);
      } finally {
        await commit("end_query");
      }
    },

    async update_gateway_info({ commit }) {
      try {
        await commit("start_query");
        const response = await axios.get("/api/gateway/info", {});
        await commit("set_gateway_info", { gateway_info: response.data });
        return response.data;
      } catch (error) {
        console.error(error);
      } finally {
        await commit("end_query");
      }
    },

    async update_plugin_info({ commit }, { plugin }) {
      try {
        await commit("start_query");
        const response = await axios.get("/api/plugin/info", {
          params: {
            plugin: plugin,
          },
        });
        await commit("set_plugin_info", {
          plugin_info: response.data[plugin],
          plugin_name: plugin,
        });
        return response.data;
      } catch (error) {
        console.error(error);
      } finally {
        await commit("end_query");
      }
    },

    async get_plugin_nested_keys({ commit }, { plugin }) {
      try {
        await commit("start_query");
        const response = await axios.get("/api/plugin/nested/keys", {
          params: {
            plugin: plugin,
          },
        });
        await commit("set_plugin_nested_keys", {
          plugin_name: plugin,
          keys: response.data,
        });
        return response.data;
      } catch (error) {
        console.error(error);
      } finally {
        await commit("end_query");
      }
    },

    async get_plugin_nested_info({ commit }, { plugin, key }) {
      try {
        await commit("start_query");
        const response = await axios.get("/api/plugin/nested/info", {
          params: {
            plugin: plugin,
            key: key,
          },
        });
        await commit("set_plugin_nested_info", {
          plugin_name: plugin,
          key: key,
          info: response.data,
        });
        return response.data;
      } catch (error) {
        console.error(error);
      } finally {
        await commit("end_query");
      }
    },

    async get_record_info({ state, commit }, { record_name }) {
      if (record_name in state.record_info) {
        return state.record_info[record_name];
      }
      try {
        await commit("start_query");
        const response = await axios.get("/api/pv/info", {
          params: { pv: record_name },
        });
        for (const [rec, rec_info] of Object.entries(response.data)) {
          await commit("add_record_info", {
            record: rec,
            info: rec_info,
          });
        }
        return response.data;
      } catch (error) {
        console.error(error);
      } finally {
        await commit("end_query");
      }
    },

    async get_ioc_records({ commit }, { ioc_name }) {
      try {
        await commit("start_query");
        const response = await axios.get("/api/ioc/pvs", {
          params: { ioc: ioc_name, pv: "*" },
        });
        const records =
          response.data.matches.length > 0 ? response.data.matches[0][1] : [];
        await commit("set_ioc_records", {
          ioc_name: ioc_name,
          records: records,
        });
        return records;
      } catch (error) {
        console.error(error);
      } finally {
        await commit("end_query");
      }
    },

    async get_file_info({ commit }, { filename }) {
      try {
        await commit("start_query");
        const response = await axios.get("/api/file/info", {
          params: {
            file: filename,
          },
        });
        await commit("set_file_info", {
          filename: filename,
          info: response.data,
        });
        return response.data;
      } catch (error) {
        console.error(error);
      } finally {
        await commit("end_query");
      }
    },

    async update_duplicates({ commit }) {
      try {
        await commit("start_query");
        const response = await axios.get("/api/pv/duplicates", {
          params: {
            pattern: "*",
          },
        });
        await commit("set_duplicates", {
          duplicates: response.data.duplicates,
        });
        return response.data;
      } catch (error) {
        console.error(error);
      } finally {
        await commit("end_query");
      }
    },

    async get_pv_relations({ commit }) {
      const full = false;
      const pv_glob = "*";

      try {
        await commit("start_query");
        const response = await axios.get("/api/pv/relations", {
          params: {
            pv: pv_glob,
            glob: true,
            full: full,
          },
        });
        await commit("set_pv_relations", { data: response.data });
        return response.data;
      } catch (error) {
        console.error(error);
      } finally {
        await commit("end_query");
      }
    },

    async find_record_matches({ state, commit }, { pattern, max_pvs, regex }) {
      if (pattern == null) {
        return;
      }
      if (!regex && pattern in state.glob_to_pvs) {
        return state.glob_to_pvs[pattern];
      } else if (regex && pattern in state.regex_to_pvs) {
        return state.regex_to_pvs[pattern];
      }
      await commit("start_query");
      const query_pattern = pattern || (regex ? ".*" : "*");
      console.debug(
        "Search for PV matches:",
        query_pattern,
        regex ? "regex" : "glob"
      );

      try {
        const response = await axios.get("/api/pv/matches", {
          params: { pattern: query_pattern, max: max_pvs, regex: regex },
        });
        const matches = response.data["matches"];
        await commit("add_record_search_results", {
          pattern: pattern,
          max_pvs: max_pvs,
          pv_list: matches,
          regex: regex,
        });
        return matches;
      } catch (error) {
        console.error("Failed to get PV list from glob", error);
      } finally {
        await commit("end_query");
      }
    },
  },
});
