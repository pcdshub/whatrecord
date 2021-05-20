import {createApp} from 'vue';
import WhatRec from './App.vue';
import PrimeVue from 'primevue/config';
// import Dialog from 'primevue/dialog';
const app = createApp(WhatRec);

app.use(PrimeVue);
// app.component('Dialog', Dialog);

app.mount('#app')
