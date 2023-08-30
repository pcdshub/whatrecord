import { cached_local_store } from "./cached";
import { api_server_store } from "./api";

export function use_configured_store() {
  if (import.meta.env.WHATRECORD_CACHE_FILE_URL) {
    return cached_local_store();
  }
  if (import.meta.env.WHATRECORD_API_HOST) {
    return api_server_store();
  }
  throw new Error(
    "WHATRECORD_API_HOST and WHATRECORD_CACHE_FILE_URL unset in environment",
  );
}
