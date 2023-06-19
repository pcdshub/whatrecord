import { createApp } from "vue";
import { router } from "./router";
import { createPinia } from "pinia";

import App from "./App.vue";
import PrimeVue from "primevue/config";

import "primevue/resources/themes/saga-blue/theme.css";
import "primevue/resources/primevue.min.css";
import "primeflex/primeflex.css";
import "primeicons/primeicons.css";

const pinia = createPinia();
const app = createApp(App);

app.use(router);
app.use(PrimeVue);
app.use(pinia);
app.mount("#app");
