<template>
  <TabMenu :model="tab_menu_items" />
  <router-view />
</template>

<script>
import TabMenu from 'primevue/tabmenu';
import { plugins } from "./settings.js";

export default {
  name: "App",
  components: {
    TabMenu,
  },
  data() {
    let tab_menu_items = [
      {label: 'Records', icon: 'pi pi-fw pi-tags', to: '/'},
      {label: 'IOCs', icon: 'pi pi-fw pi-sitemap', to: '/iocs'},
      {label: 'PV Map', icon: 'pi pi-fw pi-compass', to: {name: 'pv-relations'}},
    ]
    for (const plugin of plugins) {
      tab_menu_items.push(
        {label: plugin.label, icon: plugin.icon, to: '/' + plugin.name},
      );
    }
    tab_menu_items.push(
      {label: 'Gateway', icon: 'pi pi-fw pi-shield', to: '/gateway'},
    );
    tab_menu_items.push(
      {label: 'Logs', icon: 'pi pi-fw pi-list', to: '/logs'},
    );
    return {
      tab_menu_items: tab_menu_items
    }
  },

};
</script>

<style>
.p-tabmenu	{
  margin-bottom: 5px;
}
.p-datatable-tbody {
    font-family: monospace;
    font-size: 0.9em;
}
</style>
