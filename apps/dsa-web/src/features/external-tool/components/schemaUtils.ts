import type { JsonSchema } from '../types';

export function schemaDefaults(schema: JsonSchema): Record<string, unknown> {
  const defaults: Record<string, unknown> = {};
  Object.entries(schema.properties || {}).forEach(([name, property]) => {
    if (property.default !== undefined) defaults[name] = property.default;
  });
  return defaults;
}
