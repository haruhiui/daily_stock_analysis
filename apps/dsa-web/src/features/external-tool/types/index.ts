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

export type HostedSurfaceManifest = {
  surfaceContractVersion: number;
  surfaceId: string;
  entryUrl: string;
  stylesheetUrls: string[];
};
