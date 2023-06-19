import axios from "axios";
import "es6-promise/auto";
import { defineStore } from "pinia";

import {
  State,
  Relations,
  RecordInstance,
  StoreCache,
  RecordInfoResponse,
  IocMetadata,
  PluginResults,
  Duplicates,
  CachedPVGraph,
} from "../types";
import { GatewaySettings } from "../types";
import { AxiosResponse } from "axios";
import { AxiosRequestConfig } from "axios";
import { FileInfo } from "../types";

export interface PluginInfoResponse {
  [key: string]: PluginResults;
}

export interface DuplicatesResponse {
  duplicates: Duplicates;
}

export interface IocMatches {
  matches: IocMetadata[];
}

export interface PVGetMatchesResponse {
  patterns: string[];
  regex: boolean;
  matches: string[];
}

type IocAndRecords = [IocMetadata, RecordInstance[]];

interface IocGetMatchingRecordsResponse {
  ioc_patterns: string[];
  record_patterns: string[];
  regex: boolean;
  // TODO: ew, redo this (copied from Python because I still agree)
  matches: IocAndRecords[];
}

export const api_server_store = defineStore("api-server", {
  state: () =>
    ({
      cache: null as StoreCache | null,
      duplicates: {} as Duplicates,
      file_info: {},
      gateway_info: null,
      glob_to_pvs: {},
      ioc_info: [],
      ioc_to_records: {},
      plugin_info: {},
      plugin_nested_info: {},
      pv_relations: null as Relations | null,
      queries_in_progress: 0,
      query_in_progress: false,
      record_info: {},
      regex_to_pvs: {},
      is_online: false,
      pv_graphs: {},
      queries: {},
    }) as State,
  actions: {
    async wait_for_other_queries(timeout: number) {
      const t0 = Date.now();
      console.debug(
        `Waiting for existing queries (${this.queries_in_progress}) to finish with timeout in milliseconds of timeout`,
      );
      while (this.queries_in_progress > 0) {
        await new Promise((r) => setTimeout(r, 100));
        const elapsed = Date.now() - t0;
        if (timeout > 0 && elapsed > timeout) {
          console.debug(
            "Queries still in progress, but timed out after ",
            timeout,
            "queries=",
            this.queries_in_progress,
          );
          break;
        }
      }
    },

    async run_query<T>(
      url: string,
      config: AxiosRequestConfig,
    ): Promise<AxiosResponse<T> | null> {
      console.debug(`Query ${url} started`, config.params);
      // TODO track and dedupe API requests
      // const key = [url, config.params];
      // if (key in this.queries) {
      //   this.queries[key].callbacks.push()
      // }
      this.start_query();
      try {
        return await axios.get<T>(url, config);
      } catch (error) {
        console.error(error);
        return null;
      } finally {
        console.debug(`Query ${url} finished`);
        this.end_query();
      }
    },

    async start_query() {
      this.queries_in_progress += 1;
      this.query_in_progress = true;
    },
    async end_query() {
      if (this.queries_in_progress > 0) {
        this.queries_in_progress -= 1;
      }
      if (this.queries_in_progress === 0) {
        this.query_in_progress = false;
      }
    },
    set_plugin_nested_keys({
      plugin_name,
      keys,
    }: {
      plugin_name: string;
      keys: string[];
    }) {
      if (plugin_name in this.plugin_nested_info === false) {
        this.plugin_nested_info[plugin_name] = {
          keys: [],
          info: {},
        };
      }
      this.plugin_nested_info[plugin_name].keys = keys;
    },
    set_plugin_nested_info({
      plugin_name,
      key,
      info,
    }: {
      plugin_name: string;
      key: string;
      info: PluginResults;
    }) {
      if (plugin_name in this.plugin_nested_info === false) {
        this.plugin_nested_info[plugin_name] = {
          keys: [],
          info: {},
        };
      }
      this.plugin_nested_info[plugin_name].info[key] = info;
    },

    async update_ioc_info(): Promise<IocMetadata[]> {
      if (this.ioc_info.length > 0) {
        return this.ioc_info;
      }
      const response = await this.run_query<IocMatches>("/api/ioc/matches", {
        params: { pattern: "*" },
      });
      if (!response) {
        return [];
      }
      this.ioc_info = response.data.matches;
      return response.data.matches;
    },

    async update_gateway_info(): Promise<GatewaySettings> {
      if (this.gateway_info != null) {
        return this.gateway_info;
      }
      const response = await this.run_query<GatewaySettings>(
        "/api/gateway/info",
        {},
      );
      if (!response) {
        return { path: "", glob_str: "", pvlists: {} };
      }
      this.gateway_info = response.data;
      return this.gateway_info;
    },

    async update_plugin_info({
      plugin,
    }: {
      plugin: string;
    }): Promise<PluginResults> {
      if (plugin in this.plugin_info) {
        return this.plugin_info[plugin];
      }
      const response = await this.run_query<PluginInfoResponse>(
        "/api/plugin/info",
        {
          params: {
            plugin: plugin,
          },
        },
      );

      if (!response) {
        return {
          files_to_monitor: {},
          record_to_metadata_keys: {},
          metadata: {},
          metadata_by_key: {},
          execution_info: {},
        };
      }
      this.plugin_info[plugin] = response.data[plugin];
      return this.plugin_info[plugin];
    },

    async get_record_link_graph({
      record_name,
    }: {
      record_name: string;
    }): Promise<CachedPVGraph> {
      if (record_name in this.pv_graphs) {
        return this.pv_graphs[record_name];
      }
      const response = await this.run_query<string>("/api/pv/graph", {
        params: {
          pv: record_name,
          use_glob: false,
          format: "dot",
          // graph_type: "record",
        },
      });

      if (!response) {
        return { source: "" };
      }

      this.pv_graphs[record_name] = { source: response.data };
      return this.pv_graphs[record_name];
    },

    async get_plugin_nested_keys({
      plugin,
    }: {
      plugin: string;
    }): Promise<string[]> {
      const cached = this.plugin_nested_info[plugin]?.keys ?? null;
      if (cached) {
        return cached;
      }
      const response = await this.run_query<string[]>(
        "/api/plugin/nested/keys",
        {
          params: {
            plugin: plugin,
          },
        },
      );

      if (!response) {
        return [];
      }
      this.set_plugin_nested_keys({
        plugin_name: plugin,
        keys: response.data,
      });
      return this.plugin_nested_info[plugin].keys;
    },

    async get_plugin_nested_info({
      plugin,
      key,
    }: {
      plugin: string;
      key: string;
    }): Promise<PluginResults> {
      const response = await this.run_query<PluginResults>(
        "/api/plugin/nested/info",
        {
          params: {
            plugin: plugin,
            key: key,
          },
        },
      );

      if (!response) {
        return {
          files_to_monitor: {},
          record_to_metadata_keys: {},
          metadata: {},
          metadata_by_key: {},
          execution_info: {},
        };
      }
      this.set_plugin_nested_info({
        plugin_name: plugin,
        key: key,
        info: response.data,
      });
      return response.data;
    },

    async get_record_info({ record_name }: { record_name: string }) {
      if (record_name in this.record_info) {
        return this.record_info[record_name];
      }
      const response = await this.run_query<RecordInfoResponse>(
        "/api/pv/info",
        { params: { pv: record_name } },
      );

      if (!response) {
        return {};
      }
      for (const [rec, rec_info] of Object.entries(response.data)) {
        this.record_info[rec] = rec_info as RecordInfoResponse;
      }
      return response.data;
    },

    async get_ioc_records({
      ioc_name,
    }: {
      ioc_name: string;
    }): Promise<RecordInstance[]> {
      if (ioc_name in this.ioc_to_records) {
        return this.ioc_to_records[ioc_name];
      }
      const response = await this.run_query<IocGetMatchingRecordsResponse>(
        "/api/ioc/pvs",
        { params: { ioc: ioc_name, pv: "*" } },
      );
      if (!response) {
        return [];
      }
      const records =
        response.data.matches.length > 0 ? response.data.matches[0][1] : [];
      this.ioc_to_records[ioc_name] = records;
      return records;
    },

    async get_file_info({ filename }: { filename: string }) {
      if (filename in this.file_info) {
        return this.file_info[filename];
      }
      const response = await this.run_query<FileInfo>("/api/file/info", {
        params: {
          file: filename,
        },
      });

      if (!response || !response.data.script) {
        return { script: null, ioc: null };
      }
      this.file_info[filename] = response.data;
      return response.data;
    },

    async update_duplicates(): Promise<Duplicates> {
      if (Object.keys(this.duplicates).length > 0) {
        return this.duplicates;
      }
      const response = await this.run_query<DuplicatesResponse>(
        "/api/pv/duplicates",
        {
          params: {
            pattern: "*",
          },
        },
      );

      if (!response) {
        return {};
      }
      this.duplicates = response.data.duplicates;
      return this.duplicates;
    },

    async get_pv_relations(): Promise<Relations> {
      if (this.pv_relations != null) {
        return this.pv_relations;
      }
      const full = true;
      const pv_glob = "*";
      const response = await this.run_query<Relations>("/api/pv/relations", {
        params: {
          pv: pv_glob,
          glob: true,
          full: full,
        },
      });

      if (!response) {
        return { ioc_to_pvs: {}, script_relations: {}, pv_relations: {} };
      }

      this.pv_relations = response.data;
      return response.data;
    },

    async find_record_matches({
      pattern,
      max_pvs,
      regex,
    }: {
      pattern: string;
      max_pvs: number;
      regex: boolean;
    }): Promise<string[]> {
      if (pattern == null) {
        return [];
      }
      if (!regex && pattern in this.glob_to_pvs) {
        return this.glob_to_pvs[pattern];
      } else if (regex && pattern in this.regex_to_pvs) {
        return this.regex_to_pvs[pattern];
      }
      const query_pattern = pattern || (regex ? ".*" : "*");
      console.debug(
        "Search for PV matches:",
        query_pattern,
        regex ? "regex" : "glob",
      );

      const response = await this.run_query<PVGetMatchesResponse>(
        "/api/pv/matches",
        {
          params: { pattern: query_pattern, max: max_pvs, regex: regex },
        },
      );

      if (!response) {
        return [];
      }
      const matches = response.data.matches;
      if (regex) {
        this.regex_to_pvs[pattern] = matches;
      } else {
        this.glob_to_pvs[pattern] = matches;
      }
      return matches;
    },
  },
});
