import 'es6-promise/auto';
import { createStore } from 'vuex'

const axios = require('axios').default;

export const store = createStore({
  state: () => (
    {
      glob_to_pvs: {},
      ioc_info: [],
      ioc_to_records: {},
      file_info: {},
      plugin_info: {},
      pv_relations: {},
      queries_in_progress: 0,
      query_in_progress: false,
      record_glob: "*",
      record_info: {},
    }
  ),
  mutations: {
    start_query (state) {
      state.queries_in_progress += 1;
      state.query_in_progress = true;
    },
    end_query (state) {
      if (state.queries_in_progress > 0) {
        state.queries_in_progress -= 1;
      }
      if (state.queries_in_progress === 0) {
        state.query_in_progress = false;
      }
    },
    add_record_search_results (state, { pv_glob, pv_list }) {
      state.glob_to_pvs[pv_glob] = pv_list;
    },
    set_file_info (state, { filename, info }) {
      state.file_info[filename] = info;
    },
    set_ioc_info (state, { ioc_info }) {
      state.ioc_info = ioc_info;
    },
    set_plugin_info (state, { plugin_info }) {
      state.plugin_info = plugin_info;
    },
    add_record_info (state, { record, info }) {
      state.record_info[record] = info;
    },
    set_ioc_records (state, {ioc_name, records}) {
      state.ioc_to_records[ioc_name] = records;
    },
    set_pv_relations (state, { data }) {
      state.pv_relations = data;
    },
  },
  actions: {
    async update_ioc_info ({state, commit}) {
      if (state.ioc_info.length > 0) {
        console.log("using cached ioc info");
        return;
      }
      try {
        await commit("start_query");
        const response = await axios.get(`/api/iocs/*/matches`, {})
        await commit("set_ioc_info", {ioc_info: response.data.matches});
        return response.data.matches;
      } catch (error) {
        console.error(error);
      } finally {
        await commit("end_query");
      }
    },

    async update_plugin_info ({commit}) {
      try {
        await commit("start_query");
        const response = await axios.get(`/api/plugin/info`, {})
        await commit("set_plugin_info", {plugin_info: response.data});
        return response.data;
      } catch (error) {
        console.error(error);
      } finally {
        await commit("end_query");
      }
    },

    async get_record_info ({ state, commit }, { record_name }) {
      if (record_name in state.record_info) {
        console.debug("Using cached record info for", record_name);
        return;
      }
      try {
        await commit("start_query");
        const response = await axios.get(`/api/pv/${record_name}/info`, {})
        for (const rec in response.data) {
          await commit(
            "add_record_info",
            {
              record: rec,
              info: response.data[rec],
            },
          );
        }
        return response.data;
      } catch (error) {
        console.error(error)
      } finally {
        await commit("end_query");
      }
    },

    async get_ioc_records ({commit}, { ioc_name }) {
      try {
        await commit("start_query");
        const response = await axios.get(`/api/iocs/${ioc_name}/pvs/*`, {})
        const records = (response.data.matches.length > 0) ? response.data.matches[0][1] : [];
        await commit("set_ioc_records", {ioc_name: ioc_name, records: records});
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
        const response = await axios.get(`/api/file/info`, {
          params: {
            file: filename
          }
        })
        await commit("set_file_info", { filename: filename, info: response.data });
        return response.data;
      } catch (error) {
        console.error(error)
      } finally {
        await commit("end_query");
      }
    },

    async get_pv_relations({ commit }) {
      const full = false;
      const pv_glob = "*";

      try {
        await commit("start_query");
        const response = await axios.get(`/api/pv/${pv_glob}/relations`, {
          params: {
            full: full
          }
        })
        await commit("set_pv_relations", { data: response.data });
        return response.data;
      } catch (error) {
        console.error(error)
      } finally {
        await commit("end_query");
      }
    },

    async find_record_matches ({ state, commit }, { record_glob, max_pvs }) {
      if (record_glob == null) {
        return;
      }
      if (state.record_glob === record_glob && record_glob in state.glob_to_pvs) {
        return;
      }
      await commit("start_query");
      const query_glob = record_glob == "" ? "*" : record_glob;
      console.debug("Search for PV matches:", query_glob);

      try {
        const response = await axios.get(
          `/api/pv/${query_glob}/matches`,
          {params: {max: max_pvs}}
        )
        const matches = response.data["matches"];
        await commit(
          "add_record_search_results",
          {
            pv_glob: query_glob,
            max_pvs: max_pvs,
            pv_list: matches,
          },
        );
        return matches;
      } catch (error) {
          console.error("Failed to get PV list from glob", error);
      } finally {
          await commit("end_query");
      }
    },

  },
})
