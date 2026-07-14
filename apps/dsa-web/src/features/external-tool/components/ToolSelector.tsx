import type React from 'react';
import { BarChart3, Calculator, FlaskConical, Grid3X3, LineChart, Newspaper } from 'lucide-react';
import { Card } from '../../../components/common';
import { cn } from '../../../utils/cn';
import type { ResearchToolId } from '../types';

const TOOLS: Array<{
  id: ResearchToolId;
  icon: React.ComponentType<{ className?: string }>;
  zh: string;
  en: string;
  zhDescription: string;
  enDescription: string;
}> = [
  { id: 'formula', icon: Calculator, zh: '公式画布', en: 'Formula canvas', zhDescription: '运行表达式或研究脚本', enDescription: 'Run expressions or research scripts' },
  { id: 'market_indicators', icon: LineChart, zh: '行情指标', en: 'Market indicators', zhDescription: '查看行情与指标序列', enDescription: 'Inspect market and indicator series' },
  { id: 'grid', icon: Grid3X3, zh: '网格优化', en: 'Grid optimization', zhDescription: '评估网格参数组合', enDescription: 'Evaluate grid parameter sets' },
  { id: 'methods', icon: FlaskConical, zh: '研究方法', en: 'Research methods', zhDescription: '按注册表发现可扩展方法', enDescription: 'Discover registered methods' },
  { id: 'backtest', icon: BarChart3, zh: '量化策略回测', en: 'Strategy backtest', zhDescription: '验证确定性量化策略', enDescription: 'Validate deterministic strategies' },
  { id: 'daily_report', icon: Newspaper, zh: '每日报告预览', en: 'Daily report preview', zhDescription: '预览自动化研究片段', enDescription: 'Preview automation research sections' },
];

type Props = {
  value: ResearchToolId;
  onChange: (value: ResearchToolId) => void;
  language: 'zh' | 'en';
};

export const ToolSelector: React.FC<Props> = ({ value, onChange, language }) => (
  <Card padding="md" className="overflow-hidden">
    <div className="mb-4 text-left">
      <p className="label-uppercase">{language === 'zh' ? '研究工具' : 'Research tools'}</p>
      <p className="mt-1 text-sm text-secondary-text">
        {language === 'zh' ? '选择工具后在下方工作区运行；本页不会启动额外服务。' : 'Select a tool to run below; this page starts no extra service.'}
      </p>
    </div>
    <div className="flex flex-wrap items-stretch justify-start gap-3" role="tablist" aria-label={language === 'zh' ? '研究工具' : 'Research tools'}>
      {TOOLS.map((tool) => {
        const active = value === tool.id;
        const Icon = tool.icon;
        return (
          <button
            key={tool.id}
            type="button"
            role="tab"
            aria-selected={active}
            onClick={() => onChange(tool.id)}
            className={cn(
              'min-h-24 w-full rounded-2xl border p-4 text-left transition-all sm:w-[calc(50%-0.375rem)] lg:w-[calc(33.333%-0.5rem)] xl:w-[220px]',
              'focus-visible:outline-none focus-visible:ring-4 focus-visible:ring-cyan/15',
              active
                ? 'border-cyan/35 bg-cyan/10 shadow-[0_14px_34px_hsla(var(--primary),0.10)]'
                : 'border-border/70 bg-background/45 hover:border-cyan/20 hover:bg-hover',
            )}
          >
            <span className={cn('mb-3 inline-flex h-9 w-9 items-center justify-center rounded-xl', active ? 'bg-cyan/15 text-cyan' : 'bg-muted/50 text-secondary-text')}>
              <Icon className="h-4.5 w-4.5" />
            </span>
            <span className="block text-sm font-semibold text-foreground">{language === 'zh' ? tool.zh : tool.en}</span>
            <span className="mt-1 block text-xs leading-5 text-secondary-text">{language === 'zh' ? tool.zhDescription : tool.enDescription}</span>
          </button>
        );
      })}
    </div>
  </Card>
);
