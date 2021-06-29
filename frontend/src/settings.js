export const plugins = (process.env.VUE_APP_WHATRECORD_PLUGINS || "happi").split(" ");
export const happi_enabled = plugins.indexOf("happi") >= 0;
