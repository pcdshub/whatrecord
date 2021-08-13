import { createApp } from "vue";
import { router } from "./router";
import { store } from "./store";

import App from "./App.vue";
import PrimeVue from "primevue/config";

import "primevue/resources/themes/saga-blue/theme.css";
import "primevue/resources/primevue.min.css";
import "primeflex/primeflex.css";
import "primeicons/primeicons.css";

const app = createApp(App);
app.use(router);
app.use(PrimeVue);
app.use(store);
app.mount("#app");
