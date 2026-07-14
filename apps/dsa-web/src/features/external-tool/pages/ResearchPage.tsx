import type React from 'react';
import { useCallback, useEffect, useMemo, useState } from 'react';
import { RefreshCw, Settings2 } from 'lucide-react';
import { Link } from 'react-router-dom';
import { getParsedApiError } from '../../../api/error';
import { systemConfigApi } from '../../../api/systemConfig';
import { ApiErrorAlert, AppPage, Button, Card, Input, PageHeader, Select } from '../../../components/common';
import { useUiLanguage } from '../../../contexts/UiLanguageContext';
import { parseStockListValue } from '../../../utils/stockList';
import { externalToolApi } from '../api/externalTool';
import { ResultRenderer } from '../components/ResultRenderer';
import { SchemaForm } from '../components/SchemaForm';
import { schemaDefaults } from '../components/schemaUtils';
import { ToolSelector } from '../components/ToolSelector';
import { useExternalToolTask } from '../hooks/useExternalToolTask';
import type { ResearchMethod, ResearchToolId, ExternalToolStatus } from '../types';

const today = () => new Date().toISOString().slice(0, 10);

function symbolObjects(value: string): Array<{ symbol: string }> {
  return parseStockListValue(value).map((symbol) => ({ symbol }));
}

function FormGrid({ children }: { children: React.ReactNode }) {
  return <div className="grid gap-4 md:grid-cols-2">{children}</div>;
}

export default function ResearchPage() {
  const { language } = useUiLanguage();
  const zh = language === 'zh';
  const [status, setStatus] = useState<ExternalToolStatus | null>(null);
  const [methods, setMethods] = useState<ResearchMethod[]>([]);
  const [selectedMethodId, setSelectedMethodId] = useState('');
  const [methodValuesById, setMethodValuesById] = useState<Record<string, Record<string, unknown>>>({});
  const [tool, setTool] = useState<ResearchToolId>('formula');
  const [loadError, setLoadError] = useState<unknown>(null);
  const [watchlist, setWatchlist] = useState('');
  const [form, setForm] = useState<Record<string, string>>({
    symbol: '',
    start: '2020-01-01',
    end: today(),
    mode: 'expression',
    code: 'MA(CLOSE, 20)',
    indicators: 'MA20,RSI14',
    fast: '5',
    slow: '20',
    strategy: 'ma_cross',
    customMarkdown: '',
  });
  const taskRunner = useExternalToolTask();

  const selectedMethod = useMemo(
    () => methods.find((method) => method.methodId === selectedMethodId) || null,
    [methods, selectedMethodId],
  );
  const methodValues = useMemo(() => {
    if (!selectedMethod) return {};
    return methodValuesById[selectedMethod.methodId] || {
      ...schemaDefaults(selectedMethod.inputSchema),
      ...(selectedMethod.supportsBatchSymbols ? { symbols: symbolObjects(watchlist) } : {}),
    };
  }, [methodValuesById, selectedMethod, watchlist]);

  const load = useCallback(async () => {
    setLoadError(null);
    try {
      const nextStatus = await externalToolApi.getStatus();
      setStatus(nextStatus);
      const config = await systemConfigApi.getConfig(false);
      const stockList = config.items.find((item) => item.key === 'STOCK_LIST')?.value || '';
      setWatchlist(stockList);
      setForm((current) => ({ ...current, symbol: current.symbol || parseStockListValue(stockList)[0] || '' }));
      if (nextStatus.available) {
        const response = await externalToolApi.getMethods();
        setMethods(response.methods);
        setSelectedMethodId((current) => current || response.methods[0]?.methodId || '');
      }
    } catch (error) {
      setLoadError(error);
    }
  }, []);

  useEffect(() => {
    document.title = zh ? '研究台 - DSA' : 'Research workspace - DSA';
    const timer = window.setTimeout(() => void load(), 0);
    return () => window.clearTimeout(timer);
  }, [load, zh]);

  const setField = (name: string, value: string) => setForm((current) => ({ ...current, [name]: value }));

  const run = async () => {
    taskRunner.reset();
    if (tool === 'methods') {
      if (!selectedMethodId) return;
      await taskRunner.run(() => externalToolApi.startMethod(selectedMethodId, methodValues));
      return;
    }
    let payload: Record<string, unknown>;
    if (tool === 'formula') {
      payload = { code: form.code, mode: form.mode, start: form.start, end: form.end };
    } else if (tool === 'market_indicators') {
      payload = { symbol: form.symbol, indicators: parseStockListValue(form.indicators), start: form.start, end: form.end };
    } else if (tool === 'grid') {
      payload = { symbol: form.symbol, start: form.start, end: form.end, allow_remote: true };
    } else if (tool === 'backtest') {
      payload = { symbol: form.symbol, strategy: form.strategy, fast: Number(form.fast), slow: Number(form.slow) };
    } else {
      payload = {
        config: {
          watchlist: symbolObjects(watchlist),
          methods: selectedMethodId ? [{ id: selectedMethodId, enabled: true, params: { allow_remote: true } }] : [],
          custom_title: zh ? '自定义信息' : 'Custom notes',
          custom_markdown: form.customMarkdown,
          limitations: [zh ? '本地预览不会自动同步到 GitHub Actions。' : 'Local previews are not synchronized to GitHub Actions.'],
        },
      };
    }
    await taskRunner.run(() => externalToolApi.startCapability(tool, payload));
  };

  const canRun = status?.available && !taskRunner.isRunning && (
    tool === 'formula' ? Boolean(form.code.trim())
      : tool === 'methods' ? Boolean(selectedMethodId)
        : tool === 'daily_report' ? Boolean(selectedMethodId || form.customMarkdown.trim())
          : Boolean(form.symbol.trim())
  );

  const renderWorkspace = () => {
    if (tool === 'methods') {
      return (
        <div className="space-y-4">
          <Select
            label={zh ? '研究方法' : 'Research method'}
            value={selectedMethodId}
            onChange={setSelectedMethodId}
            options={methods.map((method) => ({ value: method.methodId, label: method.title }))}
          />
          {selectedMethod ? (
            <>
              <div className="rounded-xl border border-border/60 bg-background/35 p-4 text-sm text-secondary-text">
                <p className="font-medium text-foreground">{selectedMethod.title}</p>
                {selectedMethod.description ? <p className="mt-1">{selectedMethod.description}</p> : null}
                <p className="mt-2 text-xs">method_id: <span className="font-mono">{selectedMethod.methodId}</span> · v{selectedMethod.methodVersion}</p>
              </div>
              <SchemaForm
                schema={selectedMethod.inputSchema}
                value={methodValues}
                onChange={(next) => setMethodValuesById((current) => ({ ...current, [selectedMethod.methodId]: next }))}
                language={language}
              />
            </>
          ) : null}
        </div>
      );
    }
    if (tool === 'formula') {
      return (
        <div className="space-y-4">
          <div className="grid gap-4 md:grid-cols-[180px_1fr_1fr]">
            <Select label={zh ? '运行模式' : 'Mode'} value={form.mode} onChange={(value) => setField('mode', value)} options={[{ value: 'expression', label: zh ? '表达式' : 'Expression' }, { value: 'script', label: zh ? '脚本' : 'Script' }]} />
            <Input label={zh ? '开始日期' : 'Start date'} type="date" value={form.start} onChange={(event) => setField('start', event.target.value)} />
            <Input label={zh ? '结束日期' : 'End date'} type="date" value={form.end} onChange={(event) => setField('end', event.target.value)} />
          </div>
          <label className="block text-sm font-medium text-foreground">
            {zh ? '公式代码' : 'Formula code'}
            <textarea value={form.code} onChange={(event) => setField('code', event.target.value)} rows={8} className="input-surface input-focus-glow mt-2 w-full rounded-xl border bg-transparent p-4 font-mono text-sm text-foreground focus:outline-none" />
          </label>
        </div>
      );
    }
    if (tool === 'daily_report') {
      return (
        <div className="space-y-4">
          <div className="rounded-xl border border-warning/25 bg-warning/8 p-4 text-sm text-secondary-text">
            {zh ? '当前使用 DSA 自选列表生成本地预览。它不会修改或提交 ExternalTool 仓库中的 Actions 配置。' : 'This local preview uses the DSA watchlist. It does not edit or commit the ExternalTool Actions configuration.'}
          </div>
          <Input label={zh ? 'DSA 自选列表' : 'DSA watchlist'} value={watchlist} onChange={(event) => setWatchlist(event.target.value)} hint={zh ? '逗号分隔；仅影响本次预览。' : 'Comma-separated; affects this preview only.'} />
          <Select
            label={zh ? '报告研究方法' : 'Report method'}
            value={selectedMethodId}
            onChange={setSelectedMethodId}
            options={[
              { value: '', label: zh ? '不运行研究方法（仅自定义信息）' : 'No method (custom notes only)' },
              ...methods.map((method) => ({ value: method.methodId, label: method.title })),
            ]}
          />
          <label className="block text-sm font-medium text-foreground">
            {zh ? '自定义信息（Markdown）' : 'Custom notes (Markdown)'}
            <textarea value={form.customMarkdown} onChange={(event) => setField('customMarkdown', event.target.value)} rows={6} placeholder={zh ? '例如：今日关注风险、事件日历或个人研究备注' : 'For example: risks, event calendar, or personal research notes'} className="input-surface input-focus-glow mt-2 w-full rounded-xl border bg-transparent p-4 text-sm text-foreground focus:outline-none" />
          </label>
        </div>
      );
    }
    return (
      <FormGrid>
        <Input label={zh ? '股票代码' : 'Symbol'} value={form.symbol} onChange={(event) => setField('symbol', event.target.value)} />
        {tool === 'market_indicators' ? <Input label={zh ? '指标' : 'Indicators'} value={form.indicators} onChange={(event) => setField('indicators', event.target.value)} hint={zh ? '逗号分隔' : 'Comma-separated'} /> : null}
        {tool === 'backtest' ? (
          <>
            <Select label={zh ? '策略' : 'Strategy'} value={form.strategy} onChange={(value) => setField('strategy', value)} options={[{ value: 'ma_cross', label: zh ? '均线交叉' : 'Moving-average cross' }]} />
            <Input label={zh ? '快速均线' : 'Fast window'} type="number" min={1} value={form.fast} onChange={(event) => setField('fast', event.target.value)} />
            <Input label={zh ? '慢速均线' : 'Slow window'} type="number" min={2} value={form.slow} onChange={(event) => setField('slow', event.target.value)} />
          </>
        ) : (
          <>
            <Input label={zh ? '开始日期' : 'Start date'} type="date" value={form.start} onChange={(event) => setField('start', event.target.value)} />
            <Input label={zh ? '结束日期' : 'End date'} type="date" value={form.end} onChange={(event) => setField('end', event.target.value)} />
          </>
        )}
      </FormGrid>
    );
  };

  return (
    <AppPage className="max-w-[1480px] space-y-5">
      <PageHeader
        eyebrow={zh ? 'ExternalTool 扩展' : 'ExternalTool extension'}
        title={zh ? '量化研究台' : 'Quant research workspace'}
        description={zh ? '在 DSA 中直接运行独立研究引擎。公式、指标、方法、网格和量化回测共用同一个任务与结果界面。' : 'Run the independent research engine directly in DSA. Formula, indicators, methods, grids, and strategy backtests share one task and result surface.'}
        actions={<Button variant="secondary" size="sm" onClick={() => void load()}><RefreshCw className="h-4 w-4" />{zh ? '刷新状态' : 'Refresh'}</Button>}
      />

      {loadError ? <ApiErrorAlert error={getParsedApiError(loadError)} /> : null}
      {status && !status.available ? (
        <Card className="border-warning/30 bg-warning/8">
          <p className="font-semibold text-foreground">{zh ? 'ExternalTool 当前不可用' : 'ExternalTool is unavailable'}</p>
          <p className="mt-2 text-sm text-secondary-text">{status.message || status.state}</p>
          <Link to="/settings" className="mt-4 inline-flex items-center gap-2 text-sm font-medium text-cyan hover:underline"><Settings2 className="h-4 w-4" />{zh ? '前往设置' : 'Open settings'}</Link>
        </Card>
      ) : null}

      <ToolSelector value={tool} onChange={(next) => { setTool(next); taskRunner.reset(); }} language={language} />

      <Card padding="lg">
        <div className="mb-5 flex flex-col gap-3 border-b border-border/60 pb-4 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <p className="label-uppercase">{zh ? '工作区' : 'Workspace'}</p>
            <p className="mt-1 text-sm text-secondary-text">{zh ? `本地自选 ${parseStockListValue(watchlist).length} 个标的` : `${parseStockListValue(watchlist).length} local watchlist symbols`}</p>
          </div>
          <Button onClick={() => void run()} disabled={!canRun} isLoading={taskRunner.isRunning} loadingText={taskRunner.task?.message || (zh ? '执行中' : 'Running')}>
            {zh ? '运行研究' : 'Run research'}
          </Button>
        </div>
        {renderWorkspace()}
        {taskRunner.task ? (
          <div className="mt-5 rounded-xl border border-border/60 bg-background/35 p-4">
            <div className="flex items-center justify-between gap-4 text-sm">
              <span className="text-secondary-text">{taskRunner.task.message || taskRunner.task.status}</span>
              <span className="font-mono text-foreground">{taskRunner.task.progress}%</span>
            </div>
            <div className="mt-2 h-2 overflow-hidden rounded-full bg-muted/60"><div className="h-full rounded-full bg-primary-gradient transition-all" style={{ width: `${taskRunner.task.progress}%` }} /></div>
          </div>
        ) : null}
        {taskRunner.error ? <div className="mt-5"><ApiErrorAlert error={getParsedApiError(taskRunner.error)} /></div> : null}
      </Card>

      {taskRunner.task?.status === 'completed' && taskRunner.task.result ? (
        <Card title={zh ? '研究结果' : 'Research result'} padding="lg">
          <ResultRenderer payload={taskRunner.task.result} language={language} />
        </Card>
      ) : null}
    </AppPage>
  );
}
