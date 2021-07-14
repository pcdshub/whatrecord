import 'es6-promise/auto';
import { createStore } from 'vuex'

const axios = require('axios').default;

export const store = createStore({
  state: () => (
    {
      glob_to_pvs: {},
      ioc_info: [],
      ioc_to_records: {},
      plugin_info: {},
      pv_relations: {},
      queries_in_progress: 0,
      query_in_progress: false,
      record_glob: "*",
      record_info: {},
      selected_records: [],
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
    set_ioc_info (state, { ioc_info }) {
      state.ioc_info = ioc_info;
    },
    set_plugin_info (state, { plugin_info }) {
      state.plugin_info = plugin_info;
    },
    add_record_info (state, { record, info}) {
      console.debug("Adding record info", record, info);
      state.record_info[record] = info;
    },
    set_record_glob (state, record_glob) {
      state.record_glob = record_glob;
    },
    set_selected_records (state, records) {
      state.selected_records = records;
    },
    set_ioc_records (state, {ioc_name, records}) {
      state.ioc_to_records[ioc_name] = records;
    },
    set_pv_relations (state, { data }) {
      state.pv_relations = data;
    },
  },
  actions: {
    async update_ioc_info ({commit}) {
      try {
        await commit("start_query");
        const response = await axios.get(`/api/iocs/*/matches`, {})
        await commit("set_ioc_info", {ioc_info: response.data.matches});
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
      } catch (error) {
        console.error(error);
      } finally {
        await commit("end_query");
      }
    },

    async get_record_info ({ commit, dispatch }, { record_name }) {
      try {
        await commit("start_query");
        console.debug("Getting info for record:", record_name);
        const response = await axios.get(`/api/pv/${record_name}/info`, {})
        for (const rec in response.data) {
          await dispatch(
            "add_record_info",
            {
              record: rec,
              info: response.data[rec],
            },
          );
        }
      } catch (error) {
        console.error(error)
      } finally {
        await commit("end_query");
      }
    },

    async get_ioc_records ({commit}, { ioc_name }) {
      try {
        await commit("start_query");
        console.debug("Search for IOC records:", ioc_name);
        const response = await axios.get(`/api/iocs/${ioc_name}/pvs/*`, {})
        const records = (response.data.matches.length > 0) ? response.data.matches[0][1] : [];
        console.debug("Got record listing for", ioc_name);
        await commit("set_ioc_records", {ioc_name: ioc_name, records: records});
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

    async find_record_matches ({ commit }, { record_glob, max_pvs }) {
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
      } catch (error) {
          console.error("Failed to get PV list from glob", error);
      } finally {
          await commit("end_query");
      }
    },

    set_record_glob ({commit, state, dispatch}, {record_glob, max_pvs}) {
      if (record_glob == null) {
        return;
      }
      if (state.record_glob === record_glob && record_glob in state.glob_to_pvs) {
        return;
      }
      commit("set_record_glob", record_glob);
      if (record_glob in state.glob_to_pvs === false) {
        console.debug("Finding records...", record_glob);
        dispatch("find_record_matches", {"record_glob": record_glob, "max_pvs": max_pvs});
      }
    },

    set_selected_records ({commit, state, dispatch}, { records }) {
      console.debug("Set selected records", records);
      commit("set_selected_records", records);
      for (const rec of records) {
        if (rec in state.record_info === false) {
          dispatch("get_record_info", {"record_name": rec});
        }
      }
    },

    add_record_info ({commit}, { record, info}) {
      commit("add_record_info", {record: record, info: info});
    },
  },
  getters: {
    selected_record_info (state) {
      let record_info = {};
      for (const rec of state.selected_records) {
        if (rec in state.record_info) {
          record_info[rec] = state.record_info[rec];
        }
      }
      return record_info;
    },

  }
})
