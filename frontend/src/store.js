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
    }
  ),
  mutations: {
    add_search_results (state, { pv_glob, pv_list }) {
      state.glob_to_pvs[pv_glob] = pv_list;
    },
    set_ioc_info (state, { ioc_info }) {
      state.ioc_info = ioc_info;
    },
    add_pv_info (state, { pv, info}) {
      state.record_info[pv] = info;
      // TODO how to emit?
      state.selected_records = state.selected_records + [];
    },
    set_selected_records (state, records) {
      state.selected_records = records;
    },
  },
  actions: {
    update_ioc_info ({commit, state}) {
      if (state.ioc_info.length == 0) {
        axios.get(
          `/api/iocs/*/matches`,
          {}
        ).then(
          response => {
            commit("set_ioc_info", {ioc_info: response.data.matches});
          }
        ).catch(
          error => {
            console.log(error);
          }
        )
      }
    },
  },
  getters: {

  }
})
