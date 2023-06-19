import { FullLoadContext } from ".";

export interface ConfigurationSetting {
  name: string;
  value: string;
}

export interface VariableAssignment {
  name: string;
  value: string;
}

export interface Command {
  name: string;
  arguments: string[];
}

export interface ProtocolDefinition {
  context: FullLoadContext;
  name: string;
  handlers: Record<string, HandlerDefinition>;
  variables: Record<string, string>;
  commands: Command[];
  config: Record<string, string>;
}

export interface HandlerDefinition {
  name: string;
  commands: Command[];
}

export interface StreamProtocol {
  variables: Record<string, string>;
  protocols: Record<string, ProtocolDefinition>;
  comments: string[];
  config: Record<string, string>;
  handlers: Record<string, HandlerDefinition>;
}

export interface StreamDeviceRecordAnnotation {
  protocol_file: string;
  protocol_name: string;
  protocol_args: string[];
  error?: string;
  protocol?: ProtocolDefinition;
}

export interface StreamDeviceState {
  protocols: Record<string, StreamProtocol>;
}
