import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { SchemaForm } from '../components/SchemaForm';
import { schemaDefaults } from '../components/schemaUtils';

describe('SchemaForm', () => {
  const schema = {
    type: 'object',
    required: ['symbols'],
    properties: {
      symbols: { type: 'array', items: { type: 'object' } },
      threshold: { type: 'number', default: 0.1 },
      state: { type: 'string', enum: ['out', 'long'], default: 'out' },
      partial: { type: 'boolean', default: false },
    },
  };

  it('extracts defaults without knowing the method id', () => {
    expect(schemaDefaults(schema)).toEqual({ threshold: 0.1, state: 'out', partial: false });
  });

  it('converts a symbol list into adapter objects', () => {
    const onChange = vi.fn();
    render(<SchemaForm schema={schema} value={{}} onChange={onChange} language="zh" />);
    fireEvent.change(screen.getByLabelText('symbols *'), { target: { value: 'TEST1, TEST2' } });
    expect(onChange).toHaveBeenCalledWith({ symbols: [{ symbol: 'TEST1' }, { symbol: 'TEST2' }] });
  });
});
