import * as VueRouter from 'vue-router';

import WhatRec from './views/whatrec.vue';
import ScriptView from './views/script-view.vue';

const routes = [
  { name: 'whatrec', path: '/', component: WhatRec },
  { name: 'script', path: '/script/:script', component: ScriptView },
  // { path: '/users/:username/posts/:postId', component: NotFound },
]

export const router = VueRouter.createRouter({
  history: VueRouter.createWebHistory(),
  routes: routes,
})
