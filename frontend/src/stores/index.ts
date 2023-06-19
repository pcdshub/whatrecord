import { cached_local_store } from "./cached";
import { api_server_store } from "./api";

export function use_configured_store() {
  if (import.meta.env.WHATRECORD_API_HOST) {
    return api_server_store();
  } else {
    return cached_local_store();
  }
}
