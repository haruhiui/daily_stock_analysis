import { useEffect, useRef, useState } from 'react';
import { useTheme } from 'next-themes';
import { useNavigate } from 'react-router-dom';
import { useUiLanguage } from '../../../contexts/UiLanguageContext';
import { externalToolApi } from '../../external-tool/api/externalTool';
import type { HostedSurfaceManifest } from '../../external-tool/types';

type SurfaceOptions = {
  language: 'zh' | 'en';
  theme: 'light' | 'dark';
  stylesheetUrls: string[];
  navigate: (path: string) => void;
};

type SurfaceController = {
  update: (options: Partial<SurfaceOptions>) => void;
  unmount: () => void;
};

type SurfaceModule = {
  mountHostedSurface: (container: HTMLElement, options: SurfaceOptions) => SurfaceController;
};

export type SurfaceModuleLoader = (entryUrl: string) => Promise<SurfaceModule>;

const defaultModuleLoader: SurfaceModuleLoader = (entryUrl) => import(/* @vite-ignore */ entryUrl);

export default function HostedSurfacePage({
  surfaceId = 'research',
  loadModule = defaultModuleLoader,
}: {
  surfaceId?: string;
  loadModule?: SurfaceModuleLoader;
}) {
  const containerRef = useRef<HTMLDivElement>(null);
  const controllerRef = useRef<SurfaceController | null>(null);
  const [manifest, setManifest] = useState<HostedSurfaceManifest | null>(null);
  const [error, setError] = useState<unknown>(null);
  const { language } = useUiLanguage();
  const { resolvedTheme } = useTheme();
  const navigate = useNavigate();
  const theme = resolvedTheme === 'dark' ? 'dark' : 'light';

  useEffect(() => {
    let active = true;
    setManifest(null);
    setError(null);
    externalToolApi.getSurface(surfaceId)
      .then((result) => {
        if (active) setManifest(result);
      })
      .catch((reason: unknown) => {
        if (active) {
          console.error('Hosted surface manifest failed to load', reason);
          setError(reason);
        }
      });
    return () => { active = false; };
  }, [surfaceId]);

  useEffect(() => {
    if (!manifest || !containerRef.current) return undefined;
    let active = true;
    const container = containerRef.current;
    loadModule(manifest.entryUrl)
      .then((surfaceModule) => {
        if (!active) return;
        if (typeof surfaceModule.mountHostedSurface !== 'function') {
          throw new Error('Hosted surface entry is invalid');
        }
        controllerRef.current = surfaceModule.mountHostedSurface(container, {
          language,
          theme,
          stylesheetUrls: manifest.stylesheetUrls,
          navigate,
        });
      })
      .catch((reason: unknown) => {
        if (active) {
          console.error('Hosted surface module failed to load', reason);
          setError(reason);
        }
      });
    return () => {
      active = false;
      controllerRef.current?.unmount();
      controllerRef.current = null;
    };
    // The mounted surface is updated by the effect below instead of being recreated.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [loadModule, manifest, navigate]);

  useEffect(() => {
    controllerRef.current?.update({ language, theme, navigate });
  }, [language, navigate, theme]);

  if (error) {
    return (
      <div className="flex min-h-[55vh] items-center justify-center px-4">
        <div className="w-full max-w-lg rounded-2xl border border-danger/30 bg-card p-6 text-center shadow-soft-card">
          <h1 className="text-lg font-semibold text-foreground">
            {language === 'zh' ? '研究页面加载失败' : 'Research surface failed to load'}
          </h1>
          <p className="mt-2 text-sm text-secondary-text">
            {language === 'zh' ? '请确认外部工具已安装并启用，然后重试。' : 'Check that the external tool is installed and enabled, then retry.'}
          </p>
          <button type="button" className="btn-primary mt-5" onClick={() => window.location.reload()}>
            {language === 'zh' ? '重新加载' : 'Reload'}
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="min-w-0">
      {!manifest ? (
        <div className="flex min-h-[55vh] items-center justify-center" aria-label={language === 'zh' ? '正在加载研究页面' : 'Loading research surface'}>
          <div className="h-8 w-8 animate-spin rounded-full border-2 border-cyan/20 border-t-cyan" />
        </div>
      ) : null}
      <div ref={containerRef} className={manifest ? 'min-w-0' : 'hidden'} data-hosted-surface={surfaceId} />
    </div>
  );
}
