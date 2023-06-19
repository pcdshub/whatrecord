import axios from "axios";
import "es6-promise/auto";
import { defineStore } from "pinia";
import wcmatch from "wildcard-match";

import {
  State,
  Relations,
  RecordInstance,
  StoreCache,
  RecordInfoResponse,
  FullLoadContext,
  CachedStartupScript,
  IocMetadata,
  PluginResults,
  Duplicates,
  FileInfo,
} from "../types";
import { GatewaySettings } from "../types";

export const cached_local_store = defineStore("cached", {
  state: () =>
    ({
      cache: null as StoreCache | null,
      duplicates: {} as Duplicates,
      file_info: {} as Record<string, FileInfo>,
      gateway_info: null as GatewaySettings | null,
      glob_to_pvs: {} as Record<string, string[]>,
      ioc_info: [] as IocMetadata[],
      ioc_to_records: {} as Record<string, RecordInstance[]>,
      plugin_info: {},
      plugin_nested_info: {},
      pv_relations: null as Relations | null,
      queries_in_progress: 0,
      query_in_progress: false,
      record_info: {},
      regex_to_pvs: {},
      is_online: false,
    }) as State,
  actions: {
    async wait_for_other_queries(timeout: number) {
      const t0 = Date.now();
      console.debug(
        `Waiting for existing queries (${this.queries_in_progress}) to finish with timeout in milliseconds of ${timeout}`,
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
      func: () => Promise<T>,
      default_on_error: T | null = null,
    ) {
      console.debug("Query", func.name, "started");
      this.start_query();
      try {
        return await func();
      } catch (error) {
        console.error(error);
        return default_on_error;
      } finally {
        console.debug("Query", func.name, "finished");
        this.end_query();
      }
    },

    start_query() {
      this.queries_in_progress += 1;
      this.query_in_progress = true;
      console.debug(
        "Start query: queries in progress=",
        this.queries_in_progress,
      );
    },
    end_query() {
      if (this.queries_in_progress > 0) {
        this.queries_in_progress -= 1;
      }
      if (this.queries_in_progress === 0) {
        this.query_in_progress = false;
      }
      console.debug(
        "End query: queries in progress=",
        this.queries_in_progress,
      );
    },
    add_record_search_results(
      this: State,
      {
        pattern,
        pv_list,
        regex,
      }: { pattern: string; pv_list: string[]; regex: boolean },
    ) {
      if (regex) {
        this.regex_to_pvs[pattern] = pv_list;
      } else {
        this.glob_to_pvs[pattern] = pv_list;
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

    set_ioc_records({
      ioc_name,
      records,
    }: {
      ioc_name: string;
      records: RecordInstance[];
    }) {
      this.ioc_to_records[ioc_name] = records;
    },

    set_pv_relations({ data }: { data: Relations }) {
      if (this.cache === null) {
        throw new Error("cache empty?");
      }
      this.pv_relations = data;
      if (Object.keys(data.ioc_to_pvs).length > 0) {
        return;
      }

      // Fill up the IOC to PV list dynamically, since the server deems it
      // redundant and unnecessary to resend:
      for (const [iocname, ioc_info] of Object.entries(this.cache.iocs)) {
        const records = Array.from(
          Object.keys(ioc_info.ioc.shell_state.database),
        ).concat(
          Array.from(Object.keys(ioc_info.ioc.shell_state.pva_database)),
        );
        data.ioc_to_pvs[iocname] = Array.from(new Set(records)).sort();
        // TODO: add unknowns
      }
    },

    async download_cache(): Promise<StoreCache> {
      console.debug(
        "Downloading cached whatrecord server data from ",
        import.meta.env.WHATRECORD_CACHE_FILE_URL,
      );
      const response = await axios.get(
        import.meta.env.WHATRECORD_CACHE_FILE_URL,
        {
          decompress: true,
          headers: {
            "Content-Type": "application/json",
            Accept: "application/gzip",
          },
        },
      );
      return response.data;
    },

    async load_cached_whatrecord_data(): Promise<StoreCache> {
      if (this.cache != null) {
        console.debug("Using cached whatrecord data");
        return this.cache;
      }

      if (this.query_in_progress) {
        await this.wait_for_other_queries(5000);
        if (this.cache != null) {
          console.debug("Avoided hitting the cache again");
          return this.cache;
        }
      }

      const cache = await this.run_query<StoreCache>(this.download_cache);
      if (!cache) {
        throw new Error("Unable to download cached whatrecord data");
      }
      this.cache = cache;
      return cache;
    },

    async update_ioc_info(): Promise<IocMetadata[]> {
      if (this.ioc_info.length > 0) {
        return this.ioc_info;
      }
      const cache: StoreCache = await this.load_cached_whatrecord_data();
      const ioc_info = Object.values(cache.iocs).map((ioc) => ioc.md);
      this.ioc_info = ioc_info;
      return ioc_info;
    },

    async update_gateway_info(): Promise<GatewaySettings> {
      if (this.gateway_info !== null) {
        return this.gateway_info;
      }
      const cache: StoreCache = await this.load_cached_whatrecord_data();
      const info = cache.plugins["gateway"].metadata as GatewaySettings;
      this.gateway_info = info;
      return info;
    },

    async update_plugin_info({
      plugin,
    }: {
      plugin: string;
    }): Promise<PluginResults> {
      if (plugin in this.plugin_info) {
        return this.plugin_info[plugin];
      }
      const cache: StoreCache = await this.load_cached_whatrecord_data();
      const info = cache.plugins[plugin];
      this.plugin_info[plugin] = info;
      return info;
    },

    async get_plugin_nested_keys({
      plugin,
    }: {
      plugin: string;
    }): Promise<string[]> {
      if (plugin in this.plugin_info) {
        const keys = this.plugin_nested_info[plugin].keys ?? null;
        if (keys !== null) {
          return keys;
        }
      }
      const cache: StoreCache = await this.load_cached_whatrecord_data();
      const plug: PluginResults = cache.plugins[plugin];
      if (!plug || !plug.nested) {
        return [];
      }
      const keys: string[] = Array.from(Object.keys(plug.nested));
      this.set_plugin_nested_keys({
        plugin_name: plugin,
        keys: keys,
      });
      return keys;
    },

    async get_plugin_nested_info({
      plugin,
      key,
    }: {
      plugin: string;
      key: string;
    }): Promise<PluginResults | undefined> {
      if (plugin in this.plugin_info) {
        const info = this.plugin_nested_info[plugin]?.info[key] ?? null;
        if (info !== null) {
          return info;
        }
      }
      const cache: StoreCache = await this.load_cached_whatrecord_data();
      const info = cache.plugins[plugin].nested?.[key];
      if (info != null) {
        this.set_plugin_nested_info({
          plugin_name: plugin,
          key: key,
          info: info,
        });
      }
      return info;
    },

    async get_record_link_graph({ record_name }: { record_name: string }) {
      const cache: StoreCache = await this.load_cached_whatrecord_data();
      return cache?.pv_graphs[record_name] ?? "";
    },

    async get_record_info({ record_name }: { record_name: string }) {
      if (record_name in this.record_info) {
        return this.record_info[record_name];
      }
      const cache: StoreCache = await this.load_cached_whatrecord_data();

      let result: RecordInfoResponse = {
        pv_name: record_name,
        present: false,
        info: [],
      };
      for (const ioc_info of Object.values(cache.iocs)) {
        const ioc = ioc_info.ioc; // .md
        const v3_record = ioc.shell_state.database[record_name];
        if (v3_record != null) {
          result.present = true;
          const whatrec = {
            name: record_name,
            ioc: ioc_info.md,
            record: {
              definition:
                ioc.shell_state.database_definition?.record_types[
                  v3_record.record_type
                ] ?? null,
              instance: v3_record,
            },
            pva_group: null,
          };
          // TODO: Why is this so convoluted? refactor this on both ends!
          result.info.push(whatrec);
        }

        const v4_record = ioc.shell_state.pva_database[record_name];
        if (v4_record != null) {
          const whatrec = {
            name: record_name,
            ioc: ioc_info.md,
            record: null,
            pva_group: v4_record,
          };
          result.info.push(whatrec);
        }
      }
      this.record_info[record_name] = result;
    },

    async get_ioc_records({
      ioc_name,
    }: {
      ioc_name: string;
    }): Promise<RecordInstance[]> {
      if (ioc_name in this.ioc_to_records) {
        return this.ioc_to_records[ioc_name];
      }

      const cache: StoreCache = await this.load_cached_whatrecord_data();
      const ioc: CachedStartupScript = cache.iocs[ioc_name];

      if (!ioc) {
        return [];
      }
      const v3_records: RecordInstance[] = Array.from(
        Object.values(ioc.ioc.shell_state.database),
      );
      const v4_records: RecordInstance[] = Array.from(
        Object.values(ioc.ioc.shell_state.pva_database),
      );
      const records: RecordInstance[] = v3_records.concat(v4_records);
      this.ioc_to_records[ioc_name] = records;
      return records;
    },

    async get_file_info({ filename }: { filename: string }) {
      if (filename in this.file_info) {
        return this.file_info[filename];
      }
      const cache: StoreCache = await this.load_cached_whatrecord_data();
      const cached_file_info = cache.files[filename];
      if (cached_file_info.script !== null) {
        this.file_info[filename] = {
          script: cached_file_info.script,
          ioc: cached_file_info.ioc,
        };
      } else if (cached_file_info.raw) {
        const line_by_line_info = cached_file_info.raw.lines.map(
          (line, lineno) => ({
            context: [[filename, lineno + 1]] as FullLoadContext,
            line: line,
          }),
        );
        const script = { path: filename, lines: line_by_line_info };
        this.file_info[filename] = { script: script, ioc: null };
      }
    },

    async update_duplicates(): Promise<Duplicates> {
      if (Object.keys(this.duplicates).length) {
        return this.duplicates;
      }

      const cache: StoreCache = await this.load_cached_whatrecord_data();
      let dupes: Record<string, string[]> = {};
      for (const [iocname, ioc_info] of Object.entries(cache.iocs)) {
        for (const pvname of Object.keys(ioc_info.ioc.shell_state.database)) {
          if (pvname in dupes === false) {
            dupes[pvname] = [];
          }
          dupes[pvname].push(iocname);
        }
        for (const pvname of Object.keys(
          ioc_info.ioc.shell_state.pva_database,
        )) {
          if (pvname in dupes === false) {
            dupes[pvname] = [];
          }
          dupes[pvname].push(iocname);
        }
      }
      for (const [pvname, iocs] of Object.entries(dupes)) {
        if (iocs.length <= 1) {
          delete dupes[pvname];
        }
      }
      this.duplicates = dupes;
      return dupes;
    },

    async get_pv_relations(): Promise<Relations> {
      if (this.pv_relations !== null) {
        return this.pv_relations;
      }

      const cache: StoreCache = await this.load_cached_whatrecord_data();
      this.set_pv_relations({ data: cache.pv_relations });
      return cache.pv_relations;
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

      const cache: StoreCache = await this.load_cached_whatrecord_data();

      let matcher = null;
      if (regex) {
        try {
          const re = new RegExp(pattern);
          // re goes out of scope otherwise:
          matcher = re.test.bind(re);
        } catch (e) {
          console.warn("Invalid regular expression:", pattern, e);
          return [];
        }
      } else {
        matcher = wcmatch(pattern);
      }

      let matches: string[] = [];
      for (const ioc_info of Object.values(cache.iocs)) {
        const ioc = ioc_info.ioc; // .md
        for (const name of Object.keys(ioc.shell_state.database)) {
          if (matcher(name)) {
            matches.push(name);
          }
        }
        for (const name of Object.keys(ioc.shell_state.pva_database)) {
          if (matcher(name)) {
            matches.push(name);
          }
        }
      }
      this.add_record_search_results({
        pattern: pattern,
        pv_list: Array.from(new Set(matches)).sort(),
        regex: regex,
      });

      if (max_pvs > 0) {
        return matches.slice(0, max_pvs);
      }
      return matches;
    },
  },
});
