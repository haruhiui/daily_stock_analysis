import { beforeEach, describe, expect, it, vi } from 'vitest';
import { externalToolApi } from '../api/externalTool';

const { get } = vi.hoisted(() => ({ get: vi.fn() }));

vi.mock('../../../api', () => ({ default: { get } }));

describe('externalToolApi', () => {
  beforeEach(() => vi.clearAllMocks());

  it('loads status and converts snake_case fields', async () => {
    get.mockResolvedValueOnce({ data: { enabled: true, available: true, state: 'available', contract_version: 1, capabilities: [] } });
    const result = await externalToolApi.getStatus();
    expect(get).toHaveBeenCalledWith('/api/v1/external-tool/status');
    expect(result.contractVersion).toBe(1);
  });

  it('loads a generic hosted surface manifest', async () => {
    get.mockResolvedValueOnce({
      data: {
        surface_contract_version: 1,
        surface_id: 'research',
        entry_url: '/api/v1/external-tool/surfaces/research/assets/research-surface.js',
        stylesheet_urls: ['/api/v1/external-tool/surfaces/research/assets/research-surface.css'],
      },
    });

    const result = await externalToolApi.getSurface('research');

    expect(get).toHaveBeenCalledWith('/api/v1/external-tool/surfaces/research');
    expect(result.entryUrl).toContain('research-surface.js');
    expect(result.stylesheetUrls).toHaveLength(1);
  });
});
