export interface SafeErrorFields extends Record<string, unknown> {
  errorCode: string;
  errorPhase?: string;
}

const SAFE_PHASES = new Set([
  "config",
  "transport",
  "model",
  "tool",
  "react",
  "output",
  "persistence",
]);

export function safeErrorFields(error: unknown): SafeErrorFields {
  const source = isRecord(error) ? error : {};
  const phase = typeof source.phase === "string" && SAFE_PHASES.has(source.phase)
    ? source.phase
    : undefined;
  return {
    errorCode: safeErrorCode(error),
    ...(phase ? { errorPhase: phase } : {}),
  };
}

export function safeErrorCode(error: unknown): string {
  if (isRecord(error)
    && typeof error.code === "string"
    && /^[A-Z][A-Z0-9_]{0,127}$/.test(error.code)) {
    return error.code;
  }
  return "UNCLASSIFIED_ERROR";
}

export function safeLogUrl(value: string): string {
  return value.replace(/https?:\/\/[^\s<>"']+/gi, (candidate) => sanitizeHttpUrl(candidate));
}

function sanitizeHttpUrl(value: string): string {
  try {
    const url = new URL(value);
    const credentials = url.username || url.password ? "[REDACTED]@" : "";
    const host = `${url.hostname}${url.port ? `:${url.port}` : ""}`;
    const query = url.search ? "?[REDACTED_QUERY]" : "";
    const fragment = url.hash ? "#[REDACTED_FRAGMENT]" : "";
    return `${url.protocol}//${credentials}${host}${url.pathname}${query}${fragment}`;
  } catch {
    return "[REDACTED_URL]";
  }
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}
