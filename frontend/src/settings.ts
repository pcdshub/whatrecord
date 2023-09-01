export const enabled_plugins = (
  import.meta.env.WHATRECORD_PLUGINS || "happi twincat_pytmc netconfig"
).split(" ");
export const plugins_only_mode = import.meta.env.WHATRECORD_PLUGINS_ONLY == "1";
export const happi_enabled = enabled_plugins.indexOf("happi") >= 0;
export const netconfig_enabled = enabled_plugins.indexOf("netconfig") >= 0;
export const twincat_pytmc_enabled =
  enabled_plugins.indexOf("twincat_pytmc") >= 0;
export const epicsarch_enabled = enabled_plugins.indexOf("epicsarch") >= 0;

export interface Plugin {
  name: string;
  label: string;
  icon: string;
}

let _plugin_info: Plugin[] = [
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

export const plugins: Plugin[] = _plugin_info.filter(
  (plugin) => enabled_plugins.indexOf(plugin.name) >= 0,
);
