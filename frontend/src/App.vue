<template>
  <TabMenu :model="tab_menu_items" />
  <router-view />
</template>

<script>
import TabMenu from 'primevue/tabmenu';

export default {
  name: "App",
  components: {
    TabMenu,
  },
  data() {
    return {
      tab_menu_items: [
        {label: 'Records', icon: 'pi pi-fw pi-tags', to: '/'},
        {label: 'IOCs', icon: 'pi pi-fw pi-sitemap', to: '/iocs'},
      ]
    }
  }

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
