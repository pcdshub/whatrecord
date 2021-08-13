export const enabled_plugins = (
  process.env.VUE_APP_WHATRECORD_PLUGINS || "happi twincat_pytmc"
).split(" ");
export const happi_enabled = enabled_plugins.indexOf("happi") >= 0;
export const twincat_pytmc_enabled =
  enabled_plugins.indexOf("twincat_pytmc") >= 0;
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
];

export const plugins = _plugin_info.filter(
  (plugin) => enabled_plugins.indexOf(plugin.name) >= 0
);
