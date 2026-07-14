import { render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import ResearchPage from '../pages/ResearchPage';

const { getStatus, getMethods, getConfig, run, reset } = vi.hoisted(() => ({
  getStatus: vi.fn(),
  getMethods: vi.fn(),
  getConfig: vi.fn(),
  run: vi.fn(),
  reset: vi.fn(),
}));

vi.mock('../api/externalTool', () => ({
  externalToolApi: { getStatus, getMethods },
}));

vi.mock('../../../api/systemConfig', () => ({
  systemConfigApi: { getConfig },
}));

vi.mock('../hooks/useExternalToolTask', () => ({
  useExternalToolTask: () => ({ task: null, error: null, isRunning: false, run, reset }),
}));

describe('ResearchPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    getStatus.mockResolvedValue({ enabled: true, available: true, state: 'available', capabilities: [] });
    getConfig.mockResolvedValue({ items: [{ key: 'STOCK_LIST', value: 'TEST1,TEST2' }] });
    getMethods.mockResolvedValue({
      methodCount: 2,
      methods: [
        { methodId: 'first_method', methodVersion: 1, title: '首个示例', description: '', inputSchema: { type: 'object', properties: {} }, outputViews: ['summary'], supportsBatchSymbols: true },
        { methodId: 'future_method', methodVersion: 1, title: '后续方法', description: '', inputSchema: { type: 'object', properties: {} }, outputViews: ['table'], supportsBatchSymbols: true },
      ],
    });
  });

  it('renders six left-aligned tools without naming one method in the page title', async () => {
    render(<MemoryRouter><ResearchPage /></MemoryRouter>);
    expect(await screen.findByRole('heading', { name: '量化研究台' })).toBeInTheDocument();
    expect(screen.getAllByRole('tab')).toHaveLength(6);
    expect(screen.getByRole('tablist')).toHaveClass('justify-start');
    expect(screen.queryByRole('heading', { name: /私有方法/ })).not.toBeInTheDocument();
  });

  it('discovers multiple methods through the generic registry response', async () => {
    render(<MemoryRouter><ResearchPage /></MemoryRouter>);
    await screen.findByRole('heading', { name: '量化研究台' });
    screen.getByRole('tab', { name: /研究方法/ }).click();
    await waitFor(() => expect(screen.getByRole('option', { name: '后续方法' })).toBeInTheDocument());
  });
});
