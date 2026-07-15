import apiClient from '../../../api';
import { toCamelCase } from '../../../api/utils';
import type { ExternalToolStatus, HostedSurfaceManifest } from '../types';

export const EXTERNAL_TOOL_CONFIG_CHANGED_EVENT = 'external-tool-config-changed';

export const externalToolApi = {
  async getStatus(): Promise<ExternalToolStatus> {
    const response = await apiClient.get<Record<string, unknown>>('/api/v1/external-tool/status');
    return toCamelCase<ExternalToolStatus>(response.data);
  },

  async getSurface(surfaceId: string): Promise<HostedSurfaceManifest> {
    const response = await apiClient.get<Record<string, unknown>>(
      `/api/v1/external-tool/surfaces/${encodeURIComponent(surfaceId)}`,
    );
    return toCamelCase<HostedSurfaceManifest>(response.data);
  },
};
