import { defineConfig, loadEnv } from "vite";
import vue from "@vitejs/plugin-vue";

import * as path from "path";

// https://vitejs.dev/config/
export default defineConfig(({ command, mode }) => {
  // Load env file based on `mode` in the current working directory.
  // Set the third parameter to '' to load all env regardless of the `VITE_` prefix.
  const env = loadEnv(mode, process.cwd(), "");
  console.log(
    "Starting up whatrecord frontend on port",
    env.WHATRECORD_FRONTEND_PORT,
  );
  if (env.WHATRECORD_CACHE_FILE_URL) {
    console.log(
      "Backend-less mode with cached file expected at: " +
        env.WHATRECORD_CACHE_FILE_URL,
    );
  } else if (env.WHATRECORD_API_HOST) {
    console.log(
      "Expecting whatrecord backend server to be running on http://" +
        env.WHATRECORD_API_HOST +
        ":" +
        env.WHATRECORD_API_PORT,
    );
  } else {
    console.error(
      "Misconfiguration detected - no backend server or cache file set",
    );
  }
  return {
    define: {
      __APP_ENV__: env.APP_ENV,
      __VUE_PROD_DEVTOOLS__: mode !== "production",
    },
    // base: "./",
    mode: mode,
    plugins: [vue()],
    envPrefix: "WHATRECORD_",
    resolve: {
      alias: {
        "@": path.resolve(__dirname, "./src"),
      },
      extensions: [".mjs", ".js", ".ts", ".jsx", ".tsx", ".json", ".vue"],
      // TODO: migrate to: import HelloWorld from "@/components/HelloWorld.vue";
      // per  https://vueschool.io/articles/vuejs-tutorials/how-to-migrate-from-vue-cli-to-vite/
    },
    server: {
      port: env.WHATRECORD_FRONTEND_PORT,
      strictPort: true,
      proxy: {
        "^/api": {
          target:
            "http://" +
            env.WHATRECORD_API_HOST +
            ":" +
            env.WHATRECORD_API_PORT +
            "/",
        },
      },
    },
  };
});
