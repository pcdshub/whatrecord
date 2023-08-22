import * as VueRouter from "vue-router";
import { RouteRecordRaw } from "vue-router";

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
import LclsEpicsArchView from "./views/lcls_epicsarch.vue";

import {
  happi_enabled,
  twincat_pytmc_enabled,
  netconfig_enabled,
  epicsarch_enabled,
} from "./settings.ts";

import { nullable_string_to_array } from "./util";

let routes: RouteRecordRaw[] = [
  {
    path: "/",
    redirect: "/whatrec/*/",
  },
  {
    name: "whatrec",
    path: "/whatrec",
    component: WhatRec,
    props: (route) => ({
      pattern: route.query.pattern ?? "*",
      use_regex: route.query.regex === "true",
      record: nullable_string_to_array(route.query.record),
    }),
  },
  {
    name: "file",
    path: "/file",
    component: ScriptView,
    props: (route) => ({
      filename: route.query.filename,
      line: route.query.line ? parseInt(route.query.line.toString()) : 0,
    }),
  },
  {
    name: "iocs",
    path: "/iocs/",
    component: IocView,
    props: (route) => ({
      selected_iocs: nullable_string_to_array(route.query.ioc),
      ioc_filter: route.query.ioc_filter ?? "",
      record_filter: route.query.record_filter ?? "",
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
    path: "/plugins/happi",
    component: HappiView,
    props: (route) => ({
      item_name: route.query.item || null,
    }),
  });
}

if (twincat_pytmc_enabled) {
  routes.push({
    name: "twincat_pytmc",
    path: "/plugins/twincat_pytmc",
    component: TwincatPytmcView,
    props: (route) => ({
      plc: route.query.plc || null,
      item_name: route.query.item || null,
    }),
  });
}

if (netconfig_enabled) {
  routes.push({
    name: "netconfig",
    path: "/plugins/netconfig",
    component: NetconfigView,
    props: (route) => ({
      item_name: route.query.item || null,
    }),
  });
}

if (epicsarch_enabled) {
  routes.push({
    name: "epicsarch",
    path: "/plugins/epicsarch",
    component: LclsEpicsArchView,
    props: (route) => ({
      item_name: route.query.item || null,
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
    const app = document.getElementById("app");
    if (app !== null) {
      app.scrollIntoView();
    }
  },
});
