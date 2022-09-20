export const enabled_plugins = (
  process.env.VUE_APP_WHATRECORD_PLUGINS || "happi twincat_pytmc netconfig"
).split(" ");
export const happi_enabled = enabled_plugins.indexOf("happi") >= 0;
export const netconfig_enabled = enabled_plugins.indexOf("netconfig") >= 0;
export const twincat_pytmc_enabled =
  enabled_plugins.indexOf("twincat_pytmc") >= 0;
export const epicsarch_enabled = enabled_plugins.indexOf("epicsarch") >= 0;
let _plugin_info = [
  {
    name: "happi",
    label: "happi",
    icon: "pi pi-info-circle",
  },
  {
    name: "twincat_pytmc",
    label: "TwinCAT",
    icon: "pi pi-chevron-circle-up",
  },
  {
    name: "netconfig",
    label: "Netconfig",
    icon: "pi pi-chevron-circle-down",
  },
  {
    name: "epicsarch",
    label: "epicsArch",
    icon: "pi pi-star-o",
  },
];

export const plugins = _plugin_info.filter(
  (plugin) => enabled_plugins.indexOf(plugin.name) >= 0
);
