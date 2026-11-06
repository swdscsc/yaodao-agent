import type { HTTPStreamHandlers, HTTPStreamRequest } from "../host";
import { encodeUTF8 } from "../http/utf8";
import { parseAbsoluteHTTPURL } from "../http/url";
import { AgentError } from "../runtime/errors";
import {
  customModelCircuitKey,
  KVBackedCircuitBreaker,
  type ModelCircuitBreaker,
} from "./circuitBreaker";
import { runOpenAIStream, type RawHTTPHandle } from "./openaiStream";
import { toWireMessage } from "./platform";
import type {
  ChatModel,
  ModelRequest,
  ModelRunContext,
  ModelRunHandle,
  ModelStreamHandlers,
} from "./types";

export interface OpenAICompatibleChatModelOptions {
  id: string;
  baseUrl: string;
  apiKeySecretKey: string;
  model: string;
  headers?: Record<string, string>;
  extraBody?: Record<string, unknown>;
  allowInsecureHttp?: boolean;
  circuitBreaker?: ModelCircuitBreaker | false;
}

const PROTECTED_HEADERS = new Set([
  "authorization",
  "host",
  "content-length",
  "connection",
  "x-agent-session-id",
  "x-agent-turn-id",
  "x-agent-tool-call-id",
  "x-request-id",
  "idempotency-key",
]);

const EXTRA_BODY_ALLOWLIST = new Set([
  "top_p",
  "frequency_penalty",
  "presence_penalty",
  "seed",
  "response_format",
  "stop",
]);

export class OpenAICompatibleChatModel implements ChatModel {
  readonly id: string;
  private readonly endpoint: string;
  private readonly apiKeySecretKey: string;
  private readonly model: string;
  private readonly headers: Record<string, string>;
  private readonly extraBody: Record<string, unknown>;
  private readonly circuitBreaker?: ModelCircuitBreaker;

  constructor(options: OpenAICompatibleChatModelOptions) {
    this.id = options.id;
    this.endpoint = normalizeChatEndpoint(options.baseUrl, options.allowInsecureHttp === true);
    this.apiKeySecretKey = options.apiKeySecretKey;
    this.model = requiredValue(options.model, "Custom model is required");
    this.headers = validateHeaders(options.headers ?? {});
    this.extraBody = validateExtraBody(options.extraBody ?? {});
    this.circuitBreaker = options.circuitBreaker === false
      ? undefined
      : options.circuitBreaker ?? new KVBackedCircuitBreaker({
        key: customModelCircuitKey(options.baseUrl, this.model),
      });
  }

  run(request: ModelRequest, handlers: ModelStreamHandlers, context: ModelRunContext): ModelRunHandle {
    context.cancellation.throwIfCancelled();
    this.circuitBreaker?.beforeRequest();
    const apiKey = host.secretGet(context.sessionId, this.apiKeySecretKey);
    if (!apiKey) {
      throw new AgentError("AGENT_MODEL_CONFIG_INVALID", "Custom model credential is unavailable", {
        phase: "config",
      });
    }
    const body: Record<string, unknown> = {
      ...this.extraBody,
      model: this.model,
      messages: request.messages.map(toWireMessage),
      tools: request.tools,
      tool_choice: request.toolChoice,
      temperature: request.temperature,
      max_tokens: request.maxTokens,
      stream: true,
      stream_options: { include_usage: true },
      parallel_tool_calls: false,
    };
    const handle = runOpenAIStream(request.modelCallId, handlers, (httpHandlers) => {
      const headers: Array<[string, string]> = [
        ["Authorization", `Bearer ${apiKey}`],
        ["Accept", "text/event-stream, application/json"],
        ["Content-Type", "application/json"],
        ...Object.entries(this.headers),
      ];
      const hostRequest: HTTPStreamRequest = {
        method: "POST",
        url: this.endpoint,
        headers,
        body: encodeUTF8(JSON.stringify(body)),
        firstByteTimeoutMs: request.firstFrameTimeoutMs,
        idleTimeoutMs: request.idleTimeoutMs,
        totalTimeoutMs: request.totalTimeoutMs ?? request.timeoutMs,
      };
      let terminal = false;
      let streamId = "";
      let unsubscribe: () => void = () => undefined;
      const wrapped: HTTPStreamHandlers = {
        onHeaders: httpHandlers.onHeaders,
        onChunk: httpHandlers.onChunk,
        onDone: () => {
          if (terminal) return;
          terminal = true;
          unsubscribe();
          httpHandlers.onDone?.();
        },
        onError: (error) => {
          if (terminal) return;
          terminal = true;
          unsubscribe();
          httpHandlers.onError?.(error);
        },
      };
      streamId = host.httpStreamStart(hostRequest, wrapped);
      const cancel = (reason?: string): void => {
        if (terminal) return;
        terminal = true;
        unsubscribe();
        host.httpStreamCancel(streamId);
        httpHandlers.onError?.({
          code: "AGENT_CANCELLED",
          message: reason || "Agent operation cancelled",
          retryable: false,
        });
      };
      unsubscribe = context.cancellation.onCancel(cancel);
      return { id: streamId, cancel } satisfies RawHTTPHandle;
    }, {
      untrustedErrorMessage: "Custom model request failed",
    });
    const completed = handle.completed.then(
      (result) => {
        this.circuitBreaker?.recordSuccess();
        return result;
      },
      (error: unknown) => {
        if (shouldRecordCircuitFailure(error)) this.circuitBreaker?.recordFailure();
        throw error;
      },
    );
    return { ...handle, completed };
  }
}

function shouldRecordCircuitFailure(error: unknown): boolean {
  if (!(error instanceof AgentError)) return true;
  return error.retryable
    || error.code === "AGENT_UPSTREAM_ERROR"
    || error.code === "AGENT_UPSTREAM_TIMEOUT"
    || error.code === "AGENT_MODEL_PROTOCOL_ERROR";
}

function normalizeChatEndpoint(value: string, allowInsecure: boolean): string {
  const parsed = parseAbsoluteHTTPURL(value, allowInsecure);
  if (!parsed) {
    throw new AgentError("AGENT_MODEL_CONFIG_INVALID", "Custom model URL is not allowed", {
      phase: "config",
    });
  }
  const base = `${parsed.scheme}://${parsed.authority}${parsed.path.replace(/\/+$/, "")}`;
  return base.endsWith("/chat/completions") ? base : `${base}/chat/completions`;
}

function requiredValue(value: string, message: string): string {
  const normalized = value.trim();
  if (!normalized) throw new AgentError("AGENT_MODEL_CONFIG_INVALID", message, { phase: "config" });
  return normalized;
}

function validateHeaders(headers: Record<string, string>): Record<string, string> {
  const validated: Record<string, string> = {};
  for (const [key, value] of Object.entries(headers)) {
    if (PROTECTED_HEADERS.has(key.toLowerCase()) || /[\r\n]/.test(key + value)) {
      throw new AgentError("AGENT_MODEL_CONFIG_INVALID", `Custom header ${key} is not allowed`, {
        phase: "config",
      });
    }
    validated[key] = value;
  }
  return validated;
}

function validateExtraBody(extra: Record<string, unknown>): Record<string, unknown> {
  for (const key of Object.keys(extra)) {
    if (!EXTRA_BODY_ALLOWLIST.has(key)) {
      throw new AgentError("AGENT_MODEL_CONFIG_INVALID", `Custom body field ${key} is not allowed`, {
        phase: "config",
      });
    }
  }
  return { ...extra };
}
