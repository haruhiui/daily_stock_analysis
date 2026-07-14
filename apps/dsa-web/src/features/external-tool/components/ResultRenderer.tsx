import type React from 'react';
import { AlertTriangle, CheckCircle2 } from 'lucide-react';
import { Card, JsonViewer } from '../../../components/common';

type Props = {
  payload: Record<string, unknown>;
  language: 'zh' | 'en';
};

function record(value: unknown): Record<string, unknown> | null {
  return value && typeof value === 'object' && !Array.isArray(value) ? value as Record<string, unknown> : null;
}

function primitives(row: Record<string, unknown>): string[] {
  return Object.keys(row).filter((key) => ['string', 'number', 'boolean'].includes(typeof row[key])).slice(0, 8);
}

function formatValue(value: unknown): string {
  if (value === null || value === undefined || value === '') return '--';
  if (typeof value === 'number') return Number.isInteger(value) ? String(value) : value.toFixed(4).replace(/0+$/, '').replace(/\.$/, '');
  return String(value);
}

export const ResultRenderer: React.FC<Props> = ({ payload, language }) => {
  const outer = record(payload.result) || payload;
  const data = record(outer.result) || outer;
  const summary = record(data.summary);
  const rows = Array.isArray(data.rows) ? data.rows.filter((item): item is Record<string, unknown> => Boolean(record(item))) : [];
  const warnings = Array.isArray(data.warnings) ? data.warnings : [];
  const failedItems = Array.isArray(data.failedItems) ? data.failedItems : [];
  const columns = rows[0] ? primitives(rows[0]) : [];
  const firstHistory = rows.find((item) => Array.isArray(item.history))?.history;

  return (
    <div className="space-y-4" aria-live="polite">
      <div className="flex items-center gap-2 text-sm font-medium text-success">
        <CheckCircle2 className="h-4 w-4" />
        {language === 'zh' ? '研究任务已完成' : 'Research task completed'}
      </div>

      {summary ? (
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          {Object.entries(summary).map(([key, value]) => (
            <Card key={key} padding="sm" className="bg-background/35">
              <p className="text-xs uppercase tracking-wide text-muted-text">{key.replaceAll('_', ' ')}</p>
              <p className="mt-2 text-xl font-semibold text-foreground">{formatValue(value)}</p>
            </Card>
          ))}
        </div>
      ) : null}

      {rows.length > 0 && columns.length > 0 ? (
        <div className="overflow-x-auto rounded-2xl border border-border/70">
          <table className="min-w-full divide-y divide-border/70 text-sm">
            <thead className="bg-muted/30 text-left text-xs uppercase tracking-wide text-secondary-text">
              <tr>{columns.map((column) => <th key={column} className="px-4 py-3 font-medium">{column.replaceAll('_', ' ')}</th>)}</tr>
            </thead>
            <tbody className="divide-y divide-border/50 bg-card/35">
              {rows.slice(0, 100).map((row, index) => (
                <tr key={`${String(row.symbol || 'row')}-${index}`} className="hover:bg-hover/60">
                  {columns.map((column) => <td key={column} className="whitespace-nowrap px-4 py-3 text-foreground">{formatValue(row[column])}</td>)}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : null}

      {Array.isArray(firstHistory) && firstHistory.length > 0 ? (
        <details className="rounded-2xl border border-border/70 bg-background/35 p-4" open>
          <summary className="cursor-pointer text-sm font-semibold text-foreground">
            {language === 'zh' ? '解释时间序列' : 'Explanation time series'}
          </summary>
          <div className="mt-3 overflow-x-auto">
            <table className="min-w-full text-xs">
              <tbody>
                {firstHistory.slice(-24).map((item, index) => (
                  <tr key={index} className="border-t border-border/40">
                    {Object.entries(record(item) || {}).filter(([, value]) => typeof value !== 'object').slice(0, 8).map(([key, value]) => (
                      <td key={key} className="whitespace-nowrap px-3 py-2"><span className="text-muted-text">{key}: </span>{formatValue(value)}</td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </details>
      ) : null}

      {(warnings.length > 0 || failedItems.length > 0) ? (
        <div className="rounded-2xl border border-warning/30 bg-warning/8 p-4 text-sm text-foreground">
          <div className="mb-2 flex items-center gap-2 font-medium"><AlertTriangle className="h-4 w-4 text-warning" />{language === 'zh' ? '警告与失败项' : 'Warnings and failed items'}</div>
          <ul className="space-y-1 text-secondary-text">
            {warnings.map((item, index) => <li key={`warning-${index}`}>• {formatValue(item)}</li>)}
            {failedItems.map((item, index) => <li key={`failed-${index}`}>• {JSON.stringify(item)}</li>)}
          </ul>
        </div>
      ) : null}

      <details className="rounded-2xl border border-border/70 bg-background/35 p-4">
        <summary className="cursor-pointer text-sm font-medium text-secondary-text">{language === 'zh' ? '结构化结果' : 'Structured result'}</summary>
        <JsonViewer data={payload} className="mt-3" />
      </details>
    </div>
  );
};
