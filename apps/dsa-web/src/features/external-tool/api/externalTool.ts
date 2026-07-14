import apiClient from '../../../api';
import { toCamelCase } from '../../../api/utils';
import type {
  JsonSchema,
  ResearchMethod,
  ResearchMethodsResponse,
  ResearchToolId,
  ExternalToolStatus,
  ExternalToolTaskAccepted,
  ExternalToolTaskStatus,
} from '../types';

type RawResearchMethod = {
  method_id?: unknown;
  method_version?: unknown;
  title?: unknown;
  description?: unknown;
  input_schema?: unknown;
  output_views?: unknown;
  supports_batch_symbols?: unknown;
};

function normalizeMethod(value: unknown): ResearchMethod {
  const raw = (value && typeof value === 'object' ? value : {}) as RawResearchMethod;
  return {
    methodId: String(raw.method_id || ''),
    methodVersion: Number(raw.method_version || 0),
    title: String(raw.title || raw.method_id || ''),
    description: raw.description == null ? undefined : String(raw.description),
    // JSON Schema property names are adapter input keys and must remain untouched.
    inputSchema: (raw.input_schema && typeof raw.input_schema === 'object' ? raw.input_schema : {}) as JsonSchema,
    outputViews: Array.isArray(raw.output_views) ? raw.output_views.map(String) : [],
    supportsBatchSymbols: Boolean(raw.supports_batch_symbols),
  };
}

const TASK_ROUTES: Record<Exclude<ResearchToolId, 'methods'>, string> = {
  formula: '/api/v1/external-tool/formulas/run/tasks',
  market_indicators: '/api/v1/external-tool/market-indicators/tasks',
  grid: '/api/v1/external-tool/grid/tasks',
  backtest: '/api/v1/external-tool/backtests/tasks',
  daily_report: '/api/v1/external-tool/daily-report/tasks',
};

export const EXTERNAL_TOOL_CONFIG_CHANGED_EVENT = 'external-tool-config-changed';

export const externalToolApi = {
  async getStatus(): Promise<ExternalToolStatus> {
    const response = await apiClient.get<Record<string, unknown>>('/api/v1/external-tool/status');
    return toCamelCase<ExternalToolStatus>(response.data);
  },

  async getMethods(): Promise<ResearchMethodsResponse> {
    const response = await apiClient.get<Record<string, unknown>>('/api/v1/external-tool/methods');
    const methods = Array.isArray(response.data.methods) ? response.data.methods.map(normalizeMethod) : [];
    return {
      methods,
      methodCount: Number(response.data.method_count ?? methods.length),
    };
  },

  async getMethodSchema(methodId: string): Promise<ResearchMethod> {
    const response = await apiClient.get<Record<string, unknown>>(
      `/api/v1/external-tool/methods/${encodeURIComponent(methodId)}/schema`,
    );
    return normalizeMethod(response.data);
  },

  async startMethod(methodId: string, payload: Record<string, unknown>): Promise<ExternalToolTaskAccepted> {
    const response = await apiClient.post<Record<string, unknown>>(
      `/api/v1/external-tool/methods/${encodeURIComponent(methodId)}/tasks`,
      { payload },
    );
    return toCamelCase<ExternalToolTaskAccepted>(response.data);
  },

  async startCapability(
    toolId: Exclude<ResearchToolId, 'methods'>,
    payload: Record<string, unknown>,
  ): Promise<ExternalToolTaskAccepted> {
    const response = await apiClient.post<Record<string, unknown>>(TASK_ROUTES[toolId], { payload });
    return toCamelCase<ExternalToolTaskAccepted>(response.data);
  },

  async getTask(taskId: string): Promise<ExternalToolTaskStatus> {
    const response = await apiClient.get<Record<string, unknown>>(
      `/api/v1/external-tool/tasks/${encodeURIComponent(taskId)}`,
    );
    return toCamelCase<ExternalToolTaskStatus>(response.data);
  },
};
