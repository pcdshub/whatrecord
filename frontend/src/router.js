import * as VueRouter from 'vue-router';

import WhatRec from './views/whatrec.vue';
import ScriptView from './views/script-view.vue';
import IocView from './views/iocs.vue';
import HappiView from './views/happi.vue';
import ServerLogView from './views/logs.vue';

import { happi_enabled } from './settings.js';


let routes = [
  {
      path: '/',
      redirect: '/whatrec/*/'
  },
  {
      name: 'whatrec',
      path: '/whatrec/:record_glob?/:selected_records?',
      component: WhatRec,
      props: route => (
          {
              record_glob: route.params.record_glob || "*",
              selected_records: route.params.selected_records || "",
          }
      )
  },
  {
      name: 'file',
      path: '/file/:filename/:line?',
      component: ScriptView,
      props: route => (
          {
              filename: route.params.filename || "",
              line: route.params.line || 0,
          }
      )
  },
  {
      name: 'iocs',
      path: '/iocs/:selected_iocs_in?',
      component: IocView,
      props: route => (
          {
              selected_iocs_in: route.params.selected_iocs_in || "",
              ioc_filter: route.query.ioc_filter || "",
              record_filter: route.query.record_filter || "",
          }
      )
  },
]

if (happi_enabled) {
    routes.push(
        {
            name: 'happi',
            path: '/happi/:item_name?',
            component: HappiView,
            props: route => (
                {
                    item_name: route.params.item_name || null,
                }
            )
        },
    )
}

routes.push(
    {
        name: 'logs',
        path: '/logs',
        component: ServerLogView,
    },
)

export const router = VueRouter.createRouter({
  history: VueRouter.createWebHistory(),
  routes: routes,
  scrollBehavior() {
    document.getElementById('app').scrollIntoView();
  }
})
