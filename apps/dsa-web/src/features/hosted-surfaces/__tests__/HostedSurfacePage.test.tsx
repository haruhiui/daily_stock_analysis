import { render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import HostedSurfacePage from '../pages/HostedSurfacePage';

const { getSurface } = vi.hoisted(() => ({ getSurface: vi.fn() }));

vi.mock('../../external-tool/api/externalTool', () => ({
  externalToolApi: { getSurface },
}));

vi.mock('next-themes', () => ({
  useTheme: () => ({ resolvedTheme: 'light' }),
}));

describe('HostedSurfacePage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    getSurface.mockResolvedValue({
      surfaceContractVersion: 1,
      surfaceId: 'research',
      entryUrl: '/api/v1/external-tool/surfaces/research/assets/research-surface.js',
      stylesheetUrls: ['/api/v1/external-tool/surfaces/research/assets/research-surface.css'],
    });
  });

  it('loads and mounts a hosted surface without knowing its implementation', async () => {
    const unmount = vi.fn();
    const update = vi.fn();
    const mountHostedSurface = vi.fn((container: HTMLElement, options: unknown) => {
      void container;
      void options;
      return { unmount, update };
    });
    const loadModule = vi.fn().mockResolvedValue({ mountHostedSurface });

    const view = render(
      <MemoryRouter>
        <HostedSurfacePage loadModule={loadModule} />
      </MemoryRouter>,
    );

    await waitFor(() => expect(mountHostedSurface).toHaveBeenCalled());
    expect(getSurface).toHaveBeenCalledWith('research');
    expect(loadModule).toHaveBeenCalledWith(expect.stringContaining('research-surface.js'));
    expect(mountHostedSurface.mock.calls[0][1]).toMatchObject({
      language: 'zh',
      theme: 'light',
      stylesheetUrls: [expect.stringContaining('research-surface.css')],
    });

    view.unmount();
    expect(unmount).toHaveBeenCalledOnce();
  });

  it('shows a neutral recovery message when the manifest cannot be loaded', async () => {
    getSurface.mockRejectedValueOnce(new Error('missing'));

    render(<MemoryRouter><HostedSurfacePage /></MemoryRouter>);

    expect(await screen.findByRole('heading', { name: '研究页面加载失败' })).toBeInTheDocument();
  });
});
