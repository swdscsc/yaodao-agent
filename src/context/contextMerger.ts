export type ContextRecord = Record<string, unknown>;

export function mergeContextRecords(...sources: ContextRecord[]): ContextRecord {
  let output: ContextRecord = {};
  for (const source of sources) output = mergeRecord(output, source);
  return output;
}

export function mergePreparedNluContext(
  productConfig: ContextRecord,
  deviceConfig: ContextRecord,
  requestConfig: ContextRecord,
): ContextRecord {
  return mergeContextRecords(
    flattenPreparedConfig(productConfig),
    flattenPreparedConfig(deviceConfig),
    requestConfig,
  );
}

function flattenPreparedConfig(source: ContextRecord): ContextRecord {
  return mergeContextRecords(
    source,
    record(source.nlu_property),
    record(source.nlu_properties),
    record(source.nluProperty),
    record(source.nlu),
  );
}

function mergeRecord(base: ContextRecord, override: ContextRecord): ContextRecord {
  const output: ContextRecord = { ...base };
  for (const [key, value] of Object.entries(override)) {
    const current = output[key];
    if (isRecord(current) && isRecord(value)) output[key] = mergeRecord(current, value);
    else if (value !== undefined) output[key] = clone(value);
  }
  return output;
}

function isRecord(value: unknown): value is ContextRecord {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function record(value: unknown): ContextRecord {
  return isRecord(value) ? value : {};
}

function clone<T>(value: T): T {
  if (value === undefined) return value;
  return JSON.parse(JSON.stringify(value)) as T;
}
