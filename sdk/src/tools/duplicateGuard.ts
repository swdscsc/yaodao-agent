import { AgentError } from "../runtime/errors";
import { encodeUTF8 } from "../http/utf8";

export class DuplicateToolCallGuard {
  private readonly signatures = new Set<string>();

  add(name: string, argumentsValue: string | Record<string, unknown>): void {
    const signature = toolCallSignature(name, argumentsValue);
    if (this.signatures.has(signature)) {
      throw new AgentError("AGENT_TOOL_DUPLICATE_CALL", `Duplicate tool call: ${name}`, {
        phase: "tool",
      });
    }
    this.signatures.add(signature);
  }
}

export function toolCallSignature(name: string, argumentsValue: string | Record<string, unknown>): string {
  const parsed = typeof argumentsValue === "string"
    ? parseBoundedArguments(argumentsValue)
    : boundedArgumentObject(argumentsValue);
  return `${name}\u0000${canonicalJSON(parsed)}`;
}

function parseBoundedArguments(raw: string): Record<string, unknown> {
  if (encodeUTF8(raw).length > 64 << 10) throw unsafeArguments("Tool arguments are too large");
  let parsed: unknown;
  try {
    parsed = JSON.parse(raw) as unknown;
  } catch {
    throw unsafeArguments("Tool arguments are not valid JSON");
  }
  if (!isRecord(parsed)) throw unsafeArguments("Tool arguments must be an object");
  return boundedArgumentObject(parsed);
}

function boundedArgumentObject(value: Record<string, unknown>): Record<string, unknown> {
  const pending: Array<{ value: unknown; depth: number }> = [{ value, depth: 0 }];
  const seen = new Set<object>();
  let nodes = 0;
  while (pending.length > 0) {
    const current = pending.pop()!;
    if (current.depth > 16) throw unsafeArguments("Tool arguments are too deeply nested");
    if (current.value === null || typeof current.value !== "object") continue;
    if (seen.has(current.value)) throw unsafeArguments("Tool arguments are not serializable");
    seen.add(current.value);
    nodes += 1;
    if (nodes > 4_096) throw unsafeArguments("Tool arguments are too complex");
    const children = Array.isArray(current.value) ? current.value : Object.values(current.value);
    for (const child of children) pending.push({ value: child, depth: current.depth + 1 });
  }
  const serialized = JSON.stringify(value);
  if (encodeUTF8(serialized).length > 64 << 10) throw unsafeArguments("Tool arguments are too large");
  return value;
}

function unsafeArguments(message: string): AgentError {
  return new AgentError("AGENT_TOOL_ARGUMENT_INVALID", message, { phase: "tool" });
}

function canonicalJSON(value: unknown): string {
  if (value === null || typeof value !== "object") return JSON.stringify(value);
  if (Array.isArray(value)) return `[${value.map(canonicalJSON).join(",")}]`;
  const record = value as Record<string, unknown>;
  return `{${Object.keys(record).sort().map((key) => (
    `${JSON.stringify(key)}:${canonicalJSON(record[key])}`
  )).join(",")}}`;
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}
