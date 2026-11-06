import { AgentError } from "../runtime/errors";
import { isModelContextLengthErrorPayload, modelContextLengthError } from "./contextLengthError";
import type { ModelUsage, ToolCallDelta } from "./types";

export type { ModelUsage, ToolCallDelta } from "./types";

export type OpenAIStreamEvent =
  | { type: "text.delta"; text: string }
  | { type: "tool_call.delta"; delta: ToolCallDelta }
  | { type: "usage"; usage: ModelUsage }
  | { type: "finish"; reason: string }
  | { type: "done" };

export interface SSEDecoderOptions {
  maxLineBytes?: number;
  maxEventBytes?: number;
  maxTotalBytes?: number;
  trustedErrorPayload?: boolean;
  untrustedErrorMessage?: string;
}

const DEFAULT_MAX_LINE_BYTES = 64 << 10;
const DEFAULT_MAX_EVENT_BYTES = 1 << 20;
const DEFAULT_MAX_TOTAL_BYTES = 8 << 20;

/** Incremental OpenAI-compatible SSE decoder suitable for Goja byte callbacks. */
export class OpenAICompatibleSSEDecoder {
  private readonly utf8 = new IncrementalUTF8Decoder();
  private readonly maxLineBytes: number;
  private readonly maxEventBytes: number;
  private readonly maxTotalBytes: number;
  private readonly trustedErrorPayload: boolean;
  private readonly untrustedErrorMessage: string;
  private lineBuffer = "";
  private dataLines: string[] = [];
  private eventBytes = 0;
  private totalBytes = 0;
  private ended = false;

  constructor(options: SSEDecoderOptions = {}) {
    this.maxLineBytes = positiveLimit(options.maxLineBytes, DEFAULT_MAX_LINE_BYTES);
    this.maxEventBytes = positiveLimit(options.maxEventBytes, DEFAULT_MAX_EVENT_BYTES);
    this.maxTotalBytes = positiveLimit(options.maxTotalBytes, DEFAULT_MAX_TOTAL_BYTES);
    this.trustedErrorPayload = options.trustedErrorPayload === true;
    this.untrustedErrorMessage = options.untrustedErrorMessage ?? "Model provider request failed";
  }

  push(bytes: Uint8Array): OpenAIStreamEvent[] {
    if (this.ended) {
      throw protocolError("SSE data received after stream completion");
    }
    this.totalBytes += bytes.length;
    if (this.totalBytes > this.maxTotalBytes) {
      throw protocolError("SSE stream byte limit exceeded");
    }
    this.lineBuffer += this.utf8.push(bytes);
    return this.consumeCompleteLines();
  }

  finish(): OpenAIStreamEvent[] {
    if (this.ended) return [];
    this.lineBuffer += this.utf8.finish();
    const events = this.consumeCompleteLines();
    if (this.lineBuffer) {
      events.push(...this.consumeLine(this.lineBuffer));
      this.lineBuffer = "";
    }
    events.push(...this.dispatchEvent());
    this.ended = true;
    return events;
  }

  private consumeCompleteLines(): OpenAIStreamEvent[] {
    const events: OpenAIStreamEvent[] = [];
    let newline = this.lineBuffer.indexOf("\n");
    while (newline >= 0) {
      let line = this.lineBuffer.slice(0, newline);
      this.lineBuffer = this.lineBuffer.slice(newline + 1);
      if (line.endsWith("\r")) line = line.slice(0, -1);
      events.push(...this.consumeLine(line));
      if (this.ended && this.lineBuffer.trim().length > 0) {
        throw protocolError("SSE data received after stream completion");
      }
      newline = this.lineBuffer.indexOf("\n");
    }
    if (utf8ByteLength(this.lineBuffer) > this.maxLineBytes) {
      throw protocolError("SSE line byte limit exceeded");
    }
    return events;
  }

  private consumeLine(line: string): OpenAIStreamEvent[] {
    if (utf8ByteLength(line) > this.maxLineBytes) {
      throw protocolError("SSE line byte limit exceeded");
    }
    if (line === "") return this.dispatchEvent();
    if (line.startsWith(":")) return [];

    const separator = line.indexOf(":");
    const field = separator < 0 ? line : line.slice(0, separator);
    if (field !== "data") return [];
    let value = separator < 0 ? "" : line.slice(separator + 1);
    if (value.startsWith(" ")) value = value.slice(1);
    this.eventBytes += utf8ByteLength(value);
    if (this.eventBytes > this.maxEventBytes) {
      throw protocolError("SSE event byte limit exceeded");
    }
    this.dataLines.push(value);
    return [];
  }

  private dispatchEvent(): OpenAIStreamEvent[] {
    if (this.dataLines.length === 0) return [];
    const data = this.dataLines.join("\n");
    this.dataLines = [];
    this.eventBytes = 0;
    if (data.trim() === "[DONE]") {
      this.ended = true;
      return [{ type: "done" }];
    }
    return decodeOpenAIData(data, this.trustedErrorPayload, this.untrustedErrorMessage);
  }
}

function decodeOpenAIData(
  data: string,
  trustedErrorPayload: boolean,
  untrustedErrorMessage: string,
): OpenAIStreamEvent[] {
  let decoded: unknown;
  try {
    decoded = JSON.parse(data) as unknown;
  } catch {
    throw protocolError("Malformed SSE JSON", data);
  }
  if (!isRecord(decoded)) throw protocolError("SSE JSON must be an object", data);

  const error = decoded.error;
  if (isRecord(error)) {
    if (isModelContextLengthErrorPayload(decoded)) throw modelContextLengthError();
    if (!trustedErrorPayload) {
      throw new AgentError("AGENT_UPSTREAM_ERROR", untrustedErrorMessage, {
        retryable: true,
        phase: "model",
      });
    }
    const code = stringValue(error.code) || "AGENT_UPSTREAM_ERROR";
    const message = stringValue(error.message) || "Model request failed";
    throw new AgentError(code, message, {
      retryable: booleanValue(error.retryable),
      phase: "model",
    });
  }

  const events: OpenAIStreamEvent[] = [];
  if (Array.isArray(decoded.choices)) {
    for (const rawChoice of decoded.choices) {
      if (!isRecord(rawChoice)) continue;
      const delta = rawChoice.delta;
      if (isRecord(delta)) {
        const content = stringValue(delta.content);
        if (content) events.push({ type: "text.delta", text: content });
        if (Array.isArray(delta.tool_calls)) {
          for (const rawTool of delta.tool_calls) {
            const normalized = decodeToolCallDelta(rawTool);
            if (normalized) events.push({ type: "tool_call.delta", delta: normalized });
          }
        }
      }
      const finishReason = stringValue(rawChoice.finish_reason);
      if (finishReason) events.push({ type: "finish", reason: finishReason });
    }
  }

  const usage = decodeUsage(decoded.usage);
  if (usage) events.push({ type: "usage", usage });
  return events;
}

function decodeToolCallDelta(value: unknown): ToolCallDelta | null {
  if (!isRecord(value) || !Number.isInteger(value.index)) return null;
  const delta: ToolCallDelta = { index: Number(value.index) };
  const id = stringValue(value.id);
  if (id) delta.id = id;
  const fn = value.function;
  if (isRecord(fn)) {
    const name = stringValue(fn.name);
    const args = stringValue(fn.arguments);
    if (name) delta.name = name;
    if (args !== undefined) delta.arguments = args;
  }
  return delta;
}

function decodeUsage(value: unknown): ModelUsage | null {
  if (!isRecord(value)) return null;
  const promptTokens = nonNegativeNumber(value.prompt_tokens);
  const completionTokens = nonNegativeNumber(value.completion_tokens);
  const totalTokens = nonNegativeNumber(value.total_tokens);
  if (promptTokens === null || completionTokens === null || totalTokens === null) return null;
  if (totalTokens !== promptTokens + completionTokens) {
    throw protocolError("Inconsistent model token usage");
  }
  const usage: ModelUsage = { promptTokens, completionTokens, totalTokens };
  if (isRecord(value.prompt_tokens_details)) {
    const cached = nonNegativeNumber(value.prompt_tokens_details.cached_tokens);
    if (cached !== null) {
      if (cached > promptTokens) throw protocolError("Invalid cached token usage");
      usage.cachedPromptTokens = cached;
    }
  }
  return usage;
}

class IncrementalUTF8Decoder {
  private pending: number[] = [];

  push(bytes: Uint8Array): string {
    const input = this.pending.concat(Array.from(bytes));
    this.pending = [];
    let output = "";
    let index = 0;
    while (index < input.length) {
      const first = input[index];
      let length = 0;
      let codePoint = 0;
      if (first <= 0x7f) {
        length = 1;
        codePoint = first;
      } else if (first >= 0xc2 && first <= 0xdf) {
        length = 2;
        codePoint = first & 0x1f;
      } else if (first >= 0xe0 && first <= 0xef) {
        length = 3;
        codePoint = first & 0x0f;
      } else if (first >= 0xf0 && first <= 0xf4) {
        length = 4;
        codePoint = first & 0x07;
      } else {
        throw protocolError("Invalid UTF-8 leading byte");
      }
      if (index + length > input.length) {
        this.pending = input.slice(index);
        break;
      }
      for (let offset = 1; offset < length; offset += 1) {
        const continuation = input[index + offset];
        if ((continuation & 0xc0) !== 0x80) {
          throw protocolError("Invalid UTF-8 continuation byte");
        }
        codePoint = (codePoint << 6) | (continuation & 0x3f);
      }
      if (!validCodePoint(codePoint, length)) {
        throw protocolError("Invalid UTF-8 code point");
      }
      output += codePoint <= 0xffff
        ? String.fromCharCode(codePoint)
        : String.fromCharCode(
          0xd800 + ((codePoint - 0x10000) >> 10),
          0xdc00 + ((codePoint - 0x10000) & 0x3ff),
        );
      index += length;
    }
    return output;
  }

  finish(): string {
    if (this.pending.length > 0) throw protocolError("Truncated UTF-8 sequence");
    return "";
  }
}

function validCodePoint(codePoint: number, byteLength: number): boolean {
  if (byteLength === 2 && codePoint < 0x80) return false;
  if (byteLength === 3 && codePoint < 0x800) return false;
  if (byteLength === 4 && codePoint < 0x10000) return false;
  return codePoint <= 0x10ffff && !(codePoint >= 0xd800 && codePoint <= 0xdfff);
}

function protocolError(message: string, _sample?: string): AgentError {
  return new AgentError("AGENT_MODEL_PROTOCOL_ERROR", message, {
    phase: "model",
  });
}

function positiveLimit(value: number | undefined, fallback: number): number {
  return Number.isFinite(value) && Number(value) > 0 ? Math.floor(Number(value)) : fallback;
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function stringValue(value: unknown): string | undefined {
  return typeof value === "string" ? value : undefined;
}

function booleanValue(value: unknown): boolean {
  return value === true;
}

function nonNegativeNumber(value: unknown): number | null {
  return typeof value === "number" && Number.isSafeInteger(value) && value >= 0 ? value : null;
}

function utf8ByteLength(value: string): number {
  let bytes = 0;
  for (let index = 0; index < value.length; index += 1) {
    const code = value.charCodeAt(index);
    if (code <= 0x7f) bytes += 1;
    else if (code <= 0x7ff) bytes += 2;
    else if (code >= 0xd800 && code <= 0xdbff && index + 1 < value.length) {
      const next = value.charCodeAt(index + 1);
      if (next >= 0xdc00 && next <= 0xdfff) {
        bytes += 4;
        index += 1;
      } else bytes += 3;
    } else bytes += 3;
  }
  return bytes;
}
