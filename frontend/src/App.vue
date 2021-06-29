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
    ]
    for (const plugin of plugins) {
      tab_menu_items.push(
        {label: plugin, icon: 'pi pi-fw pi-info-circle', to: '/' + plugin},
      );
    }
    return {
      tab_menu_items: tab_menu_items
    }
  },

};
</script>

<style scoped>
.p-tabmenu	{
  margin-bottom: 5px;
}
.p-grid	{
  margin: 5px;
}
</style>
