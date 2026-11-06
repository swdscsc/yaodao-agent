export type AgentErrorPhase =
  | "config"
  | "transport"
  | "model"
  | "tool"
  | "mcp"
  | "response"
  | "persistence";

export interface AgentErrorOptions {
  retryable?: boolean;
  phase?: AgentErrorPhase;
  publicDetails?: Record<string, unknown>;
}

const PUBLIC_SOURCE_CODE = /^[A-Za-z][A-Za-z0-9._:-]{0,127}$/;
const PUBLIC_FEATURE = /^[a-z][a-z0-9_]{0,63}$/;

/** Keeps the small, documented subset of server error details safe for Agent code. */
export function sanitizePublicErrorDetails(value: unknown): Record<string, unknown> | undefined {
  if (typeof value !== "object" || value === null || Array.isArray(value)) return undefined;
  const details = value as Record<string, unknown>;
  const output: Record<string, unknown> = {};
  if (typeof details.source_code === "string" && PUBLIC_SOURCE_CODE.test(details.source_code)) {
    output.source_code = details.source_code;
  }
  if (typeof details.feature === "string" && PUBLIC_FEATURE.test(details.feature)) {
    output.feature = details.feature;
  }
  return Object.keys(output).length > 0 ? output : undefined;
}

/** A bounded, device-safe error shared by the SDK runtime. */
export class AgentError extends Error {
  readonly code: string;
  readonly retryable: boolean;
  readonly phase: AgentErrorPhase;
  readonly publicDetails?: Record<string, unknown>;

  constructor(code: string, message: string, options: AgentErrorOptions = {}) {
    super(message);
    this.name = "AgentError";
    this.code = code;
    this.retryable = options.retryable ?? false;
    this.phase = options.phase ?? "model";
    this.publicDetails = sanitizePublicErrorDetails(options.publicDetails);
  }
}

export function asAgentError(
  error: unknown,
  fallbackCode = "AGENT_INTERNAL_ERROR",
  phase: AgentErrorPhase = "model",
): AgentError {
  if (error instanceof AgentError) return error;
  return new AgentError(fallbackCode, "Agent operation failed", { phase });
}
