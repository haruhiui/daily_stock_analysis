import type React from 'react';
import { Input, Select } from '../../../components/common';
import type { JsonSchema } from '../types';

type Props = {
  schema: JsonSchema;
  value: Record<string, unknown>;
  onChange: (value: Record<string, unknown>) => void;
  language: 'zh' | 'en';
};

function displayName(name: string, schema: JsonSchema): string {
  return schema.title || name.replaceAll('_', ' ');
}

function parseArray(value: string, schema: JsonSchema): unknown[] {
  const values = value.split(/[\s,;，、；]+/).map((item) => item.trim()).filter(Boolean);
  return schema.items?.type === 'object' ? values.map((symbol) => ({ symbol })) : values;
}

function inputValue(value: unknown, schema: JsonSchema): string {
  if (Array.isArray(value)) {
    return value.map((item) => typeof item === 'object' && item ? String((item as Record<string, unknown>).symbol || '') : String(item)).filter(Boolean).join(',');
  }
  if (value === undefined || value === null) return '';
  if (schema.type === 'object') return JSON.stringify(value, null, 2);
  return String(value);
}

export const SchemaForm: React.FC<Props> = ({ schema, value, onChange, language }) => {
  const required = new Set(schema.required || []);
  const setField = (name: string, next: unknown) => onChange({ ...value, [name]: next });

  return (
    <div className="grid gap-4 md:grid-cols-2">
      {Object.entries(schema.properties || {}).map(([name, property]) => {
        const label = `${displayName(name, property)}${required.has(name) ? ' *' : ''}`;
        if (property.type === 'boolean') {
          return (
            <label key={name} className="flex min-h-11 items-center gap-3 rounded-xl border border-border/70 bg-background/40 px-4 py-3 text-sm text-foreground">
              <input
                type="checkbox"
                checked={Boolean(value[name] ?? property.default)}
                onChange={(event) => setField(name, event.target.checked)}
                className="h-4 w-4 rounded border-border accent-cyan"
              />
              <span>{label}</span>
            </label>
          );
        }
        if (property.enum?.length) {
          return (
            <Select
              key={name}
              label={label}
              value={String(value[name] ?? property.default ?? '')}
              onChange={(next) => setField(name, next)}
              options={property.enum.map((item) => ({ value: String(item), label: String(item) }))}
            />
          );
        }
        const type = property.format === 'date' ? 'date' : property.type === 'number' || property.type === 'integer' ? 'number' : 'text';
        return (
          <Input
            key={name}
            label={label}
            type={type}
            step={property.type === 'integer' ? 1 : property.type === 'number' ? 'any' : undefined}
            min={property.minimum}
            max={property.maximum}
            value={inputValue(value[name] ?? property.default, property)}
            placeholder={property.type === 'array' ? (language === 'zh' ? '逗号分隔，例如 600519,300750' : 'Comma-separated, e.g. 600519,300750') : property.description}
            hint={property.description}
            onChange={(event) => {
              const raw = event.target.value;
              if (property.type === 'array') setField(name, parseArray(raw, property));
              else if (property.type === 'number' || property.type === 'integer') setField(name, raw === '' ? undefined : Number(raw));
              else setField(name, raw);
            }}
          />
        );
      })}
    </div>
  );
};
