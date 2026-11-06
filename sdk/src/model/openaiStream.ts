import type { AgentErrorObj, HTTPStreamHandlers } from "../host";
import { decodeUTF8, encodeUTF8 } from "../http/utf8";
import { AgentCancelledError } from "../runtime/cancellation";
import { AgentError, sanitizePublicErrorDetails } from "../runtime/errors";
import { isModelContextLengthErrorPayload, modelContextLengthError } from "./contextLengthError";
import { OpenAICompatibleSSEDecoder, type OpenAIStreamEvent } from "./sseDecoder";
import type {
  AssistantToolCall,
  ModelRunHandle,
  ModelRunResult,
  ModelStreamHandlers,
  ModelUsage,
  ToolCallDelta,
} from "./types";

export interface RawHTTPHandle {
  id: string;
  cancel(reason?: string): void;
}

export type StartRawHTTP = (handlers: HTTPStreamHandlers) => RawHTTPHandle;

export interface OpenAIStreamOptions {
  trustedErrorPayload?: boolean;
  untrustedErrorMessage?: string;
}

interface ToolCallParts {
  id: string;
  name: string;
  arguments: string;
}

const MAX_TOOL_CALLS = 128;
const MAX_TOOL_CALL_ID_BYTES = 128;
const MAX_TOOL_CALL_NAME_BYTES = 64;
const MAX_TOOL_CALL_ARGUMENT_BYTES = 64 << 10;

export function runOpenAIStream(
  modelCallId: string,
  handlers: ModelStreamHandlers,
  start: StartRawHTTP,
  options: OpenAIStreamOptions = {},
): ModelRunHandle {
  const decoder = new OpenAICompatibleSSEDecoder({
    trustedErrorPayload: options.trustedErrorPayload,
    untrustedErrorMessage: options.untrustedErrorMessage,
  });
  const toolParts = new Map<number, ToolCallParts>();
  const errorBody: number[] = [];
  let responseStatus = 0;
  let text = "";
  let finishReason = "";
  let usage: ModelUsage | undefined;
  let sawDone = false;
  let terminal = false;
  let rawHandle: RawHTTPHandle | undefined;
  let resolveCompleted!: (result: ModelRunResult) => void;
  let rejectCompleted!: (error: AgentError) => void;
  const completed = new Promise<ModelRunResult>((resolve, reject) => {
    resolveCompleted = resolve;
    rejectCompleted = reject;
  });

  const fail = (error: AgentError, cancelTransport: boolean): void => {
    if (terminal) return;
    terminal = true;
    rejectCompleted(error);
    if (cancelTransport) {
      try {
        rawHandle?.cancel(error.message);
      } catch {
        // Terminal settlement must not depend on transport cleanup.
      }
    }
    try {
      handlers.onError?.(error);
    } catch {
      // Observers cannot prevent the completed promise from settling.
    }
  };
  const consume = (events: OpenAIStreamEvent[]): void => {
    for (const event of events) {
      if (event.type === "text.delta") {
        text += event.text;
        handlers.onTextDelta?.(event.text);
      } else if (event.type === "tool_call.delta") {
        assembleToolDelta(toolParts, event.delta);
        handlers.onToolCallDelta?.(event.delta);
      } else if (event.type === "usage") {
        usage = event.usage;
        handlers.onUsage?.(event.usage);
      } else if (event.type === "finish") {
        finishReason = event.reason;
        handlers.onFinish?.(event.reason);
      } else if (event.type === "done") {
        sawDone = true;
      }
    }
  };

  const httpHandlers: HTTPStreamHandlers = {
    onHeaders(status): void {
      responseStatus = status;
    },
    onChunk(bytes): void {
      if (terminal) return;
      try {
        if (responseStatus >= 400) {
          if (errorBody.length + bytes.length <= 64 << 10) errorBody.push(...Array.from(bytes));
          return;
        }
        consume(decoder.push(bytes));
      } catch (error) {
        fail(toAgentError(error), true);
      }
    },
    onDone(): void {
      if (terminal) return;
      try {
        if (responseStatus >= 400) {
          fail(decodeHTTPError(responseStatus, new Uint8Array(errorBody), options), false);
          return;
        }
        consume(decoder.finish());
        if (!sawDone) throw new AgentError(
          "AGENT_MODEL_PROTOCOL_ERROR",
          "Model stream ended without [DONE]",
          { phase: "model" },
        );
        if (!text && toolParts.size === 0 && !isSafetyFinishReason(finishReason)) {
          throw new AgentError("AGENT_MODEL_EMPTY_RESPONSE", "Model stream returned no output", {
            retryable: true,
            phase: "model",
          });
        }
        const toolCalls = finalizeToolCalls(toolParts);
        terminal = true;
        resolveCompleted({ text, toolCalls, usage, finishReason: finishReason || "stop" });
      } catch (error) {
        fail(toAgentError(error), false);
      }
    },
    onError(error): void {
      fail(hostError(error, options), false);
    },
  };
  try {
    rawHandle = start(httpHandlers);
  } catch (error) {
    fail(error instanceof AgentError ? error : new AgentError(
      "AGENT_UPSTREAM_ERROR",
      "Model transport failed to start",
      { retryable: true, phase: "transport" },
    ), false);
  }

  return {
    id: modelCallId,
    completed,
    cancel(reason?: string): void {
      if (terminal) return;
      fail(new AgentCancelledError(reason), true);
    },
  };
}

function assembleToolDelta(parts: Map<number, ToolCallParts>, delta: ToolCallDelta): void {
  if (!Number.isInteger(delta.index) || delta.index < 0 || delta.index >= MAX_TOOL_CALLS) {
    throw modelProtocolError("Invalid streamed tool call index");
  }
  if (!parts.has(delta.index) && parts.size >= MAX_TOOL_CALLS) {
    throw modelProtocolError("Too many streamed tool calls");
  }
  const current = parts.get(delta.index) ?? { id: "", name: "", arguments: "" };
  if (delta.id) current.id += delta.id;
  if (delta.name) current.name += delta.name;
  if (delta.arguments !== undefined) current.arguments += delta.arguments;
  if (encodeUTF8(current.id).length > MAX_TOOL_CALL_ID_BYTES
    || encodeUTF8(current.name).length > MAX_TOOL_CALL_NAME_BYTES
    || encodeUTF8(current.arguments).length > MAX_TOOL_CALL_ARGUMENT_BYTES) {
    throw modelProtocolError("Streamed tool call exceeds field limits");
  }
  parts.set(delta.index, current);
}

function finalizeToolCalls(parts: Map<number, ToolCallParts>): AssistantToolCall[] {
  const calls: AssistantToolCall[] = [];
  const callIds = new Set<string>();
  const indexes = Array.from(parts.keys()).sort((left, right) => left - right);
  for (const index of indexes) {
    const part = parts.get(index)!;
    if (!/^[A-Za-z0-9._:-]{1,128}$/.test(part.id)
      || !/^[A-Za-z0-9_-]{1,64}$/.test(part.name)
      || callIds.has(part.id)) throw modelProtocolError("Invalid streamed tool call identity");
    callIds.add(part.id);
    calls.push({
      id: part.id,
      type: "function",
      function: { name: part.name, arguments: part.arguments },
    });
  }
  return calls;
}

function modelProtocolError(message: string): AgentError {
  return new AgentError("AGENT_MODEL_PROTOCOL_ERROR", message, { phase: "model" });
}

function isSafetyFinishReason(reason: string): boolean {
  return reason === "content_filter" || reason === "stop_sensitive";
}

function decodeHTTPError(
  status: number,
  bytes: Uint8Array,
  options: OpenAIStreamOptions,
): AgentError {
  let decoded: unknown;
  try {
    decoded = JSON.parse(decodeUTF8(bytes)) as unknown;
  } catch {
    decoded = undefined;
  }
  if (isModelContextLengthErrorPayload(decoded)) return modelContextLengthError();
  if (!options.trustedErrorPayload) {
    return new AgentError("AGENT_UPSTREAM_ERROR", options.untrustedErrorMessage ?? "Model provider request failed", {
      retryable: status === 429 || status >= 500,
      phase: "model",
    });
  }
  const body: Record<string, unknown> = isRecord(decoded) ? decoded : {};
  const code = typeof body.code === "string" ? body.code : statusCodeToError(status);
  const message = typeof body.message === "string" ? body.message : "Model request failed";
  return new AgentError(code, message, {
    retryable: status >= 500,
    phase: "model",
    publicDetails: sanitizePublicErrorDetails(body.details),
  });
}

function statusCodeToError(status: number): string {
  if (status === 401) return "AGENT_UNAUTHENTICATED";
  if (status === 403) return "AGENT_IDENTITY_MISMATCH";
  if (status === 429) return "AGENT_CHAT_QUOTA_EXCEEDED";
  if (status === 504) return "AGENT_UPSTREAM_TIMEOUT";
  return status >= 500 ? "AGENT_UPSTREAM_ERROR" : "AGENT_REQUEST_INVALID";
}

function hostError(error: AgentErrorObj, options: OpenAIStreamOptions): AgentError {
  return new AgentError(error.code, options.trustedErrorPayload
    ? error.message
    : options.untrustedErrorMessage ?? "Model provider request failed", {
    retryable: error.retryable,
    phase: "transport",
  });
}

function toAgentError(error: unknown): AgentError {
  if (error instanceof AgentError) return error;
  return new AgentError("AGENT_MODEL_PROTOCOL_ERROR", "Invalid model stream", {
    phase: "model",
  });
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}
