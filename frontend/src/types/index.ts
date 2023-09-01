import { AsynState } from "./asyn";
import { StreamDeviceState } from "./stream";

export interface PVField {
  name: string;
}

export type PVFieldRelationship = [PVField, PVField, string[]];

export type PVRelations = Record<string, Record<string, PVFieldRelationship[]>>;
export type ScriptRelations = Record<string, Record<string, string[]>>;
export type Duplicates = Record<string, string[]>;

export interface Relations {
  // IOC name to list of PV names
  ioc_to_pvs: Record<string, string[]>;
  // IOC name to related IOC name to list of PVs shared
  script_relations: ScriptRelations;
  // PV name to (PV name and field information)
  pv_relations: PVRelations;
}

export interface PluginNestedInfo {
  // Keys we can request from the server
  keys: string[];
  // Filled cache of nested information from server
  info: Record<string, PluginResults>;
}

export interface APIQuery {
  url: string;
  params: any;
  callbacks: (() => any)[];
}

export interface State {
  cache: StoreCache | null;
  duplicates: Duplicates;
  file_info: Record<string, FileInfo>;
  gateway_info: GatewaySettings | null;
  glob_to_pvs: Record<string, string[]>;
  ioc_info: IocMetadata[] | null;
  ioc_to_records: Record<string, RecordInstance[]>;
  is_online: boolean;
  plugin_info: Record<string, PluginResults>;
  plugin_nested_info: Record<string, PluginNestedInfo>;
  pv_relations: Relations;
  queries_in_progress: number;
  query_in_progress: boolean;
  record_info: Record<string, RecordInfoResponse>;
  regex_to_pvs: Record<string, string[]>;
  pv_graphs: Record<string, CachedPVGraph>;
  queries: Record<string, APIQuery>;
}

export type Context = [string, number];
export type FullLoadContext = Context[];

export interface RecordTypeField {
  context: FullLoadContext;
  name: string;
  type: string;
  asl?: string | null;
  initial?: string | null;
  promptgroup?: string | null;
  prompt?: string | null;
  special?: string | null;
  pp?: string | null;
  interest?: string | null;
  base?: string | null;
  size?: string | null;
  extra?: string | null;
  menu?: string | null;
  prop?: string | null;
  body: Record<string, string>;
}

export interface DatabaseDevice {
  record_type: string;
  link_type: string;
  dset_name: string;
  choice_string: string;
}

export interface AutosaveRestoreValue {
  context: FullLoadContext;
  pvname: string;
  record: string;
  field: string;
  value: string | string[];
}

export interface AutosaveMetadataAnnotation {
  restore?: AutosaveRestoreValue[];
  error?: string[];
  disconnected?: string[];
}

export interface AutosaveRestoreValue {
  context: FullLoadContext;
  pvname: string;
  record: string;
  field: string;
  value: string | string[];
}

export interface AutosaveRestoreError {
  context: FullLoadContext;
  number: number;
  description: string;
}

export interface AutosaveRestoreFile {
  filename: string;
  values: Record<string, Record<string, AutosaveRestoreValue>>;
  disconnected: string[];
  errors: AutosaveRestoreError[];
  comments: string[];
}

export interface AutosaveRestorePassFile {
  context: FullLoadContext;
  save_filename: string;
  macros: Record<string, string>;
  pass_number: number;

  load_timestamp: Date | null;
  file_timestamp: Date | null;
  data: AutosaveRestoreFile | null;
}

export interface AutosaveSet {
  context: FullLoadContext;
  request_filename: string;
  save_filename: string;
  period: Number | null;
  trigger_channel: string | null;
  macros: Record<string, string>;
  method: string;
}

export interface AutosaveState {
  configured: boolean;
  request_paths: string[];
  save_path: string;
  sets: Record<string, AutosaveSet>;
  restore_files: Record<string, AutosaveRestorePassFile>;
  incomplete_sets_ok: boolean | null;
  dated_backups: boolean | null;
  date_period_minutes: Number | null;
  num_seq_files: Number | null;
  seq_period: Number | null;
  retry_seconds: Number | null;
  ca_reconnect: boolean | null;
  callback_timeout: Number | null;
  task_priority: Number | null;
  nfs_host: string | null;
  use_status_pvs: boolean | null;
  status_prefix: string | null;
  file_permissions: Number | null;
  debug: Number | null;
}

export interface MotorState {}

export interface RecordType {
  context: FullLoadContext;
  name: string;
  cdefs: string[];
  fields: Record<string, RecordTypeField>;
  devices: DatabaseDevice[];
}

export interface RecordField {
  dtype: string;
  name: string;
  value: Object;
  context: FullLoadContext;
}

export interface PVAFieldReference {
  context: FullLoadContext;
  name?: string;
  record_name?: string;
  field_name?: string;
  metadata: Record<string, string>;
}

export type AnyField = RecordField | PVAFieldReference;

export interface RecordInstance {
  context: FullLoadContext;
  name: string;
  record_type: string;
  has_dbd_info: boolean;
  fields: Record<string, AnyField>;
  info: Record<string, object>;
  metadata: Record<string, object>;
  aliases: string[];
  is_grecord: boolean;
  is_pva: boolean;
  owner: string;
}

export interface DatabaseMenu {
  context: FullLoadContext;
  name: string;
  choices: Record<string, string>;
}

export interface IocshArgument {
  name: string;
  type: string;
}

export interface IocshCommand {
  name: string;
  args: IocshArgument[];
  usage?: string | null;
  context?: FullLoadContext | null;
}

export interface IocshVariable {
  name: string;
  value?: string | null;
  type?: string | null;
}

export interface IocMetadata {
  name: string;
  script: string;
  startup_directory: string;
  host?: string | null;
  port?: number | null;
  binary?: string | null;
  base_version: string;
  metadata: Record<string, Object>;
  macros: Record<string, string>;
  standin_directories: Record<string, string>;
  commands: Record<string, IocshCommand>;
  variables: Record<string, IocshVariable>;
  loaded_files: Record<string, string>;
  load_success: boolean;
}

export interface RecordDefinitionAndInstance {
  definition: RecordType | null;
  instance: RecordInstance;
}

export interface WhatRecord {
  name: string;
  record?: RecordDefinitionAndInstance | null;
  menus?: Record<string, DatabaseMenu> | null;
  pva_group?: RecordInstance | null;
  ioc?: IocMetadata | null;
}

export interface IocshRedirect {
  fileno: number;
  name: string;
  mode: string;
}

export interface IocshResultArgument {
  name: string;
  type: string;
  value: any;
}

export interface IocshResult {
  context: FullLoadContext;
  line: string;
  outputs?: string[];
  argv?: string[];
  error?: string;
  redirects?: IocshRedirect[];
  result?: Object | DatabaseLint | null;
}

export interface LinterMessage {
  name: string;
  context: FullLoadContext;
  message: string;
}

export interface DatabaseLint {
  errors: LinterMessage[];
  warnings: LinterMessage[];
}

export interface Database {
  addpaths: string[];
  aliases: Record<string, string>;
  breaktables: Record<string, string[]>;
  comments: string[];
  devices: DatabaseDevice[];
  drivers: string[];
  functions: string[];
  includes: string[];
  links: Record<string, string>;
  menus: Record<string, DatabaseMenu>;
  paths: string[];
  pva_groups: Record<string, RecordInstance>;
  record_types: Record<string, RecordType>;
  records: Record<string, RecordInstance>;
  registrars: string[];
  standalone_aliases: Record<string, string>;
  variables: Record<string, string | null>;
  lint: DatabaseLint;
}

export interface MacroContext {
  show_warnings: boolean;
  string_encoding: string;
  macros: Record<string, string>;
}

export interface HostAccessGroup {
  context: FullLoadContext;
  comments: string;
  name: string;
  hosts: string[];
}

export interface UserAccessGroup {
  context: FullLoadContext;
  comments: string;
  name: string;
  users: string[];
}

export interface AccessSecurityRule {
  context: FullLoadContext;
  comments: string;
  level: number;
  options: string;
  log_options: string | null;
  users: string[] | null;
  hosts: string[] | null;
  calc: string | null;
}

export interface AccessSecurityGroup {
  context: FullLoadContext;
  comments: string;
  name: string;
  inputs: Record<string, string>;
  rules: AccessSecurityRule[];
}

export interface AccessSecurityConfig {
  filename: string | null;
  hash: string | null;
  users: Record<string, UserAccessGroup>;
  groups: Record<string, AccessSecurityGroup>;
  hosts: Record<string, HostAccessGroup>;
  header: string;
}

export interface AccessSecurityState {
  config?: AccessSecurityConfig | null;
  filename?: string | null;
  macros?: Record<string, string>;
}

export interface GatewaySettings {
  path: string;
  glob_str: string;
  pvlists: Record<string, GatewayPVList>;
}

export interface GatewayPVList {
  filename: string | null;
  evaluation_order: string | null;
  rules: GatewayAnyRule[];
  hash: string | null;
  header: string;
}

export interface GatewayAccessSecurity {
  group: string | null;
  level: string | null;
}

export interface GatewayRule {
  context: FullLoadContext;
  pattern: string;
  command: string;
  header: string;
  metadata: Record<string, string>;
}

export interface GatewayAliasRule extends GatewayRule {
  command: "ALIAS";
  pvname: string;
  access: GatewayAccessSecurity | null;
}

export interface GatewayAllowRule extends GatewayRule {
  command: "ALLOW";
  access: GatewayAccessSecurity | null;
}

export interface GatewayDenyRule extends GatewayRule {
  command: "DENY";
  hosts: string[];
}

export type GatewayAnyRule =
  | GatewayAliasRule
  | GatewayAllowRule
  | GatewayDenyRule;

export interface GatewayMatch {
  filename: string;
  rule: GatewayRule;
  groups: string[];
}

export interface GatewayMetadata {
  matches: GatewayMatch[];
  name: string;
}

export interface ShellState {
  prompt: string;
  variables: Record<string, string>;
  string_encoding: string;
  ioc_initialized: boolean;
  standin_directories: Record<string, string>;
  working_directory: string;
  aliases: Record<string, string>;
  database_definition?: Database | null;
  database: Record<string, RecordInstance>;
  pva_database: Record<string, RecordInstance>;
  load_context: FullLoadContext;
  loaded_files: Record<string, string>;
  macro_context: MacroContext;
  ioc_info: IocMetadata;
  db_add_paths: string;
  database_grammar_version: number;
  access_security: AccessSecurityState;
  asyn: AsynState;
  autosave: AutosaveState;
  motor: MotorState;
  streamdevice: StreamDeviceState;
}

export interface IocshScript {
  path: string;
  lines: IocshResult[];
}

export interface LoadedIoc {
  name: string;
  path: string;
  metadata: IocMetadata;
  shell_state: ShellState;
  script: IocshScript;
  pv_relations: PVRelations;
  load_failure?: boolean;
}

export interface RecordInfoResponse {
  pv_name: string;
  present: boolean;
  info: WhatRecord[];
}

export interface CachedRawFile {
  lines: string[];
  path: string;
  hash: string;
}

export interface CachedStartupScript {
  ioc: LoadedIoc;
  md: IocMetadata;
}

export interface FileInfo {
  ioc: IocMetadata | null;
  script: IocshScript;
}

export interface FileInfoResponse {
  ioc: IocMetadata | null;
  script: IocshScript | null;
  raw?: CachedRawFile;
}

export interface CachedPVGraph {
  source: string;
}

export interface PluginResults {
  files_to_monitor: Record<string, string>;
  record_to_metadata_keys: Record<string, string[]>;
  metadata_by_key: Record<string, Object>;
  metadata: Object;
  execution_info: Record<string, Object>;
  nested?: Record<string, PluginResults> | null;
}

// whatrecord offline cache download -> offline store ``cache`` attribute
export interface StoreCache {
  pv_relations: Relations;
  files: Record<string, FileInfoResponse>;
  iocs: Record<string, CachedStartupScript>;
  plugins: Record<string, PluginResults>;
  pv_graphs: Record<string, CachedPVGraph>;
  logs: string[];
}
