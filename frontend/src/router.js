import * as VueRouter from "vue-router";

import WhatRec from "./views/whatrec.vue";
import ScriptView from "./views/script-view.vue";
import IocView from "./views/iocs.vue";
import HappiView from "./views/happi.vue";
import NetconfigView from "./views/netconfig.vue";
import TwincatPytmcView from "./views/twincat_pytmc.vue";
import ServerLogView from "./views/logs.vue";
import PVRelationsView from "./views/pv_relations.vue";
import GatewayView from "./views/gateway.vue";
import DuplicateView from "./views/duplicates.vue";

import { happi_enabled, twincat_pytmc_enabled, netconfig_enabled } from "./settings.js";

let routes = [
  {
    path: "/",
    redirect: "/whatrec/*/",
  },
  {
    name: "whatrec",
    path: "/whatrec/:record_glob?/:selected_records?",
    component: WhatRec,
  },
  {
    name: "file",
    path: "/file/:filename/:line?",
    component: ScriptView,
    props: (route) => ({
      filename: route.params.filename || "",
      line: route.params.line || 0,
    }),
  },
  {
    name: "iocs",
    path: "/iocs/:selected_iocs_in?",
    component: IocView,
    props: (route) => ({
      selected_iocs_in: route.params.selected_iocs_in || "",
      ioc_filter: route.query.ioc_filter || "",
      record_filter: route.query.record_filter || "",
    }),
  },
  {
    name: "pv-relations",
    path: "/pv-relations",
    component: PVRelationsView,
  },
];

if (happi_enabled) {
  routes.push({
    name: "happi",
    path: "/happi/:item_name?",
    component: HappiView,
    props: (route) => ({
      item_name: route.params.item_name || null,
    }),
  });
}

if (twincat_pytmc_enabled) {
  routes.push({
    name: "twincat_pytmc",
    path: "/twincat_pytmc/:item_name?",
    component: TwincatPytmcView,
    props: (route) => ({
      item_name: route.params.item_name || null,
    }),
  });
}

if (netconfig_enabled) {
  routes.push({
    name: "netconfig",
    path: "/netconfig/:item_name?",
    component: NetconfigView,
    props: (route) => ({
      item_name: route.params.item_name || null,
    }),
  });
}

routes.push({
  name: "duplicates",
  path: "/duplicates",
  component: DuplicateView,
});

routes.push({
  name: "logs",
  path: "/logs",
  component: ServerLogView,
});

routes.push({
  name: "gateway",
  path: "/gateway",
  component: GatewayView,
});

export const router = VueRouter.createRouter({
  history: VueRouter.createWebHistory(),
  routes: routes,
  scrollBehavior() {
    document.getElementById("app").scrollIntoView();
  },
});
