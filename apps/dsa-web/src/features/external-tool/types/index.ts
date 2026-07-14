export type ExternalToolState = 'disabled' | 'missing' | 'incompatible' | 'degraded' | 'available' | string;

export type ExternalToolStatus = {
  enabled: boolean;
  available: boolean;
  state: ExternalToolState;
  message?: string;
  contractVersion?: number;
  engineVersion?: string;
  capabilities: string[];
  supportedContract?: { min: number; max: number };
  diagnostics?: Record<string, unknown>;
};

export type JsonSchema = {
  type?: string;
  title?: string;
  description?: string;
  default?: unknown;
  format?: string;
  enum?: Array<string | number>;
  minimum?: number;
  maximum?: number;
  exclusiveMinimum?: number;
  minItems?: number;
  items?: JsonSchema;
  required?: string[];
  properties?: Record<string, JsonSchema>;
};

export type ResearchMethod = {
  methodId: string;
  methodVersion: number;
  title: string;
  description?: string;
  inputSchema: JsonSchema;
  outputViews: string[];
  supportsBatchSymbols?: boolean;
};

export type ResearchMethodsResponse = {
  methods: ResearchMethod[];
  methodCount: number;
};

export type ExternalToolTaskAccepted = {
  taskId: string;
  traceId: string;
  status: string;
  progress: number;
  message?: string;
};

export type ExternalToolTaskStatus = ExternalToolTaskAccepted & {
  error?: string | null;
  result?: Record<string, unknown> | null;
};

export type ResearchToolId =
  | 'formula'
  | 'market_indicators'
  | 'grid'
  | 'methods'
  | 'backtest'
  | 'daily_report';
