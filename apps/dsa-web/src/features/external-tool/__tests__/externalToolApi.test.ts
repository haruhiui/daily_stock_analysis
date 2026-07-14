import { beforeEach, describe, expect, it, vi } from 'vitest';
import { externalToolApi } from '../api/externalTool';

const { get, post } = vi.hoisted(() => ({ get: vi.fn(), post: vi.fn() }));

vi.mock('../../../api', () => ({ default: { get, post } }));

describe('externalToolApi', () => {
  beforeEach(() => vi.clearAllMocks());

  it('loads status and converts snake_case fields', async () => {
    get.mockResolvedValueOnce({ data: { enabled: true, available: true, state: 'available', contract_version: 1, capabilities: [] } });
    const result = await externalToolApi.getStatus();
    expect(get).toHaveBeenCalledWith('/api/v1/external-tool/status');
    expect(result.contractVersion).toBe(1);
  });

  it('uses one generic method task route for any registered method', async () => {
    post.mockResolvedValueOnce({ data: { task_id: 'task-1', trace_id: 'task-1', status: 'pending', progress: 0 } });
    await externalToolApi.startMethod('future_method', { symbols: [{ symbol: 'TEST' }] });
    expect(post).toHaveBeenCalledWith(
      '/api/v1/external-tool/methods/future_method/tasks',
      { payload: { symbols: [{ symbol: 'TEST' }] } },
    );
  });

  it('preserves dynamic JSON Schema property names from the adapter', async () => {
    get.mockResolvedValueOnce({
      data: {
        method_count: 1,
        methods: [{
          method_id: 'example',
          method_version: 1,
          title: 'Example',
          input_schema: {
            type: 'object',
            properties: {
              snake_case_parameter: { type: 'number' },
              initial_state: { type: 'string' },
            },
          },
          output_views: ['summary'],
          supports_batch_symbols: true,
        }],
      },
    });
    const response = await externalToolApi.getMethods();
    expect(response.methods[0].inputSchema.properties).toHaveProperty('snake_case_parameter');
    expect(response.methods[0].inputSchema.properties).toHaveProperty('initial_state');
    expect(response.methods[0].inputSchema.properties).not.toHaveProperty('nearThreshold');
  });

  it('maps fixed tools to their isolated task routes', async () => {
    post.mockResolvedValue({ data: { task_id: 'task-2', trace_id: 'task-2', status: 'pending', progress: 0 } });
    await externalToolApi.startCapability('formula', { code: 'CLOSE' });
    await externalToolApi.startCapability('daily_report', { config: {} });
    expect(post).toHaveBeenNthCalledWith(1, '/api/v1/external-tool/formulas/run/tasks', { payload: { code: 'CLOSE' } });
    expect(post).toHaveBeenNthCalledWith(2, '/api/v1/external-tool/daily-report/tasks', { payload: { config: {} } });
  });
});
