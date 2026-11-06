import { AgentError } from "../runtime/errors";

const CONTEXT_ERROR_CODES = new Set([
  "context_length_exceeded",
  "context_window_exceeded",
  "max_context_length_exceeded",
  "input_too_long",
  "too_many_tokens",
  "agent_model_context_length_exceeded",
]);

const CONTEXT_ERROR_MESSAGE = /maximum context length|context (?:length|window).*(?:exceed|too (?:large|long))|input tokens?.*(?:exceed|too (?:large|long))|too many tokens/i;

export function isModelContextLengthErrorPayload(value: unknown): boolean {
  if (!isRecord(value)) return false;
  const source = isRecord(value.error) ? value.error : value;
  for (const field of [source.code, source.type]) {
    if (typeof field === "string" && CONTEXT_ERROR_CODES.has(field.toLowerCase())) return true;
  }
  return typeof source.message === "string" && CONTEXT_ERROR_MESSAGE.test(source.message);
}

export function modelContextLengthError(): AgentError {
  return new AgentError(
    "AGENT_MODEL_CONTEXT_LENGTH_EXCEEDED",
    "Model context is too large",
    { phase: "model" },
  );
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}
