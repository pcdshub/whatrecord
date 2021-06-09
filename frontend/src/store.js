import 'es6-promise/auto';
import { createStore } from 'vuex'

const axios = require('axios').default;

export const store = createStore({
  state: () => (
    {
      glob_to_pvs: {},
      record_info: {},
      ioc_info: [],
      selected_records: [],
      ioc_to_records: {},
      query_in_progress: false,
      queries_in_progress: 0,
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
    add_record_info (state, { record, info}) {
      console.log("Adding record info", record, info);
      state.record_info[record] = info;
    },
    set_selected_records (state, records) {
      state.selected_records = records;
    },
    set_ioc_records (state, {ioc_name, records}) {
      state.ioc_to_records[ioc_name] = records;
    },
  },
  actions: {
    update_ioc_info ({commit}) {
      commit("start_query");
      axios.get(
        `/api/iocs/*/matches`,
        {}
      ).then(
        response => {
          commit("set_ioc_info", {ioc_info: response.data.matches});
          commit("end_query");
        }
      ).catch(
        error => {
          console.log(error);
          commit("end_query");
        }
      )
    },

    get_record_info ({ commit }, { record_name }) {
      commit("start_query");
      console.log("Getting info for record:", record_name);
      axios.get(
        `/api/pv/${record_name}/info`,
        {})
        .then(response => {
          for (const rec in response.data) {
            commit(
              "add_record_info",
              {
                record: rec,
                info: response.data[rec],
              },
            );
          }
          commit("end_query");
        })
        .catch(error => {
          console.log(error)
          commit("end_query");
        });
    },

    get_ioc_records ({commit}, { ioc_name }) {
      commit("start_query");
      console.log("Search for IOC records:", ioc_name);
      axios.get(
        `/api/iocs/${ioc_name}/pvs/*`,
        {}
      ).then(
        response => {
          const records = (response.data.matches.length > 0) ? response.data.matches[0][1] : [];
          console.log("Got record listing for", ioc_name);
          commit("set_ioc_records", {ioc_name: ioc_name, records: records});
          commit("end_query");
        }
      ).catch(
        error => {
          console.log(error);
          commit("end_query");
        }
      )
    },

    find_pv_matches ({ commit }, { pv_glob, max_pvs }) {
      commit("start_query");
      const query_glob = pv_glob == "" ? "*" : pv_glob;
      console.log("Search for PV matches:", query_glob);

      axios.get(
        `/api/pv/${query_glob}/matches`,
        {params: {max: max_pvs}}
      ).then(
        response => {
          const matches = response.data["matches"];
          commit(
            "add_record_search_results",
            {
              pv_glob: pv_glob,
              max_pvs: max_pvs,
              pv_list: matches,
            },
          );
          commit("end_query");
        }
      ).catch(
        error => {
          console.log("Failed to get PV list from glob", error);
          commit("end_query");
        }
      )
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
