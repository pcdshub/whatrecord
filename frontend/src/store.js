import 'es6-promise/auto';
import { createStore } from 'vuex'

export const store = createStore({
  state: () => (
    {
      glob_to_pvs: {},
      record_info: {},
      selected_records: [],
    }
  ),
  mutations: {
    add_search_results (state, { pv_glob, pv_list }) {
      state.glob_to_pvs[pv_glob] = pv_list;
    },
    add_pv_info (state, { pv, info}) {
      state.record_info[pv] = info;
      // TODO how to emit?
      state.selected_records = state.selected_records + [];
    },
    set_selected_records (state, records) {
      state.selected_records = records;
    }
  },
  actions: {
  },
  getters: {

  }
})
