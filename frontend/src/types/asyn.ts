import { FullLoadContext } from ".";

export interface AsynPort {
  context: FullLoadContext;
  name: string;
  options: Record<string, AsynPortOption>;
  metadata: Record<string, string>;
  motors: Record<string, AsynMotor>;
}

export interface AsynMotor {
  context: FullLoadContext;
  name: string;
  metadata: Record<string, string | number>;
  parent: string | null;
}

export interface AsynIPPort {
  hostInfo: string;
  priority: string;
  noAutoConnect: string;
  noProcessEos: string;
}

export interface AsynSerialPort {
  ttyName: string;
  priority: string;
  noAutoConnect: string;
  noProcessEos: string;
}

export interface AdsAsynPort {
  ipaddr: string;
  amsaddr: string;
  amsport: number;
  asynParamTableSize: number;
  priority: number;
  noAutoConnect: number;
  defaultSampleTimeMS: number;
  maxDelayTimeMS: number;
  adsTimeoutMS: number;
  defaultTimeSource: string;
}
export interface AsynPortMultiDevice {
  context: FullLoadContext;
  name: string;
  metadata: Record<string, Object>;
  motors: Record<string, AsynMotor>;
  devices: Record<string, AsynPortDevice>;
}

export interface AsynPortDevice {
  context: FullLoadContext;
  name: string;
  options: Record<string, AsynPortOption>;
  metadata: Record<string, string>;
  motors: Record<string, AsynMotor>;
}

export interface AsynPortOption {
  context: FullLoadContext;
  key: string;
  value: string;
}

export interface AsynMetadata {
  ports: Record<string, AsynPort>;
}

export interface AsynState {
  ports: Record<string, AsynPort>;
}
