import {createApp} from 'vue';
import WhatRec from './App.vue';
import PrimeVue from 'primevue/config';

import 'primevue/resources/themes/saga-blue/theme.css';
import 'primevue/resources/primevue.min.css';
import 'primeflex/primeflex.css';

// import Dialog from 'primevue/dialog';
const app = createApp(WhatRec);

app.use(PrimeVue);
// app.component('Dialog', Dialog);

app.mount('#app')
