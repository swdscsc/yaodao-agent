import type { HTTPStreamHandlers, HTTPStreamRequest } from "../host";
import { decodeUTF8, encodeUTF8 } from "../http/utf8";
import { AgentRuntimeTransport } from "../transport/agentRuntime";
import { AgentCancelledError, CancellationTokenSource } from "../runtime/cancellation";
import { AgentError, asAgentError } from "../runtime/errors";
import type {
  ToolCall,
  ToolExecutionContext,
  ToolExecutor,
  ToolResult,
} from "./types";
import { normalizeClosedToolResult } from "./types";

export type LocalToolHandler = (
  call: ToolCall,
  context: ToolExecutionContext,
) => ToolResult | Promise<ToolResult>;

export interface LocalToolExecutorOptions {
  handler: LocalToolHandler;
  timeoutMs?: number;
}

export class LocalToolExecutor implements ToolExecutor {
  private readonly handler: LocalToolHandler;
  private readonly timeoutMs: number;

  constructor(options: LocalToolExecutorOptions) {
    if (typeof options.handler !== "function") {
      throw new AgentError("AGENT_TOOL_BINDING_INVALID", "Local tool handler is required", {
        phase: "tool",
      });
    }
    this.handler = options.handler;
    this.timeoutMs = boundedToolTimeout(options.timeoutMs);
  }

  async execute(call: ToolCall, context: ToolExecutionContext): Promise<ToolResult> {
    context.cancellation.throwIfCancelled();
    const localCancellation = new CancellationTokenSource();
    const unsubscribeParent = context.cancellation.onCancel((reason) => localCancellation.cancel(reason));
    let timerId = "";
    let timedOut = false;
    let unsubscribeLocal: () => void = () => undefined;
    try {
      return await new Promise<ToolResult>((resolve, reject) => {
        unsubscribeLocal = localCancellation.token.onCancel((reason) => {
          if (!timedOut) reject(new AgentCancelledError(reason));
        });
        timerId = host.timerStart(this.timeoutMs, () => {
          timedOut = true;
          reject(new AgentError("AGENT_LOCAL_TOOL_TIMEOUT", "Local tool execution timed out", {
            retryable: true,
            phase: "tool",
          }));
          localCancellation.cancel("Local tool execution timed out");
        });
        Promise.resolve()
          .then(() => this.handler(call, { ...context, cancellation: localCancellation.token }))
          .then(resolve, (error: unknown) => reject(asAgentError(
            error,
            "AGENT_LOCAL_TOOL_EXECUTION_FAILED",
            "tool",
          )));
      });
    } finally {
      unsubscribeLocal();
      unsubscribeParent();
      if (timerId) host.timerCancel(timerId);
    }
  }
}

export interface PlatformToolExecutorOptions {
  baseUrl: string;
  tokenSecretKey: string;
  toolId: string;
  timeoutMs?: number;
  serverContext?: {
    type: "netease_music";
    secretRef: string;
  };
}

export class PlatformToolExecutor implements ToolExecutor {
  private readonly transport: AgentRuntimeTransport;
  private readonly toolId: string;
  private readonly timeoutMs?: number;
  private readonly serverContext?: PlatformToolExecutorOptions["serverContext"];

  constructor(options: PlatformToolExecutorOptions) {
    if (!/^[A-Za-z0-9._-]{1,128}$/.test(options.toolId)) {
      throw new AgentError("AGENT_TOOL_BINDING_INVALID", "Invalid platform tool ID", {
        phase: "tool",
      });
    }
    this.transport = new AgentRuntimeTransport(options);
    this.toolId = options.toolId;
    this.timeoutMs = options.timeoutMs;
    if (options.serverContext && options.toolId !== "platform.system.media_agent_bridge") {
      throw new AgentError("AGENT_TOOL_BINDING_INVALID", "Server context is not allowed for this platform tool", {
        phase: "tool",
      });
    }
    this.serverContext = options.serverContext;
  }

  async execute(call: ToolCall, context: ToolExecutionContext): Promise<ToolResult> {
    const response = await this.transport.requestJSON<unknown>({
      path: `/tools/${this.toolId}/invoke`,
      body: {
        arguments: call.parsedArguments,
        context: {
          model_tool_name: call.name,
          ...(context.userText ? { user_text: context.userText } : {}),
          ...this.resolveServerContext(context.sessionId),
        },
      },
      context: {
        sessionId: context.sessionId,
        turnId: context.turnId,
        requestId: context.requestId,
        appId: context.appId,
        toolCallId: call.id,
      },
      totalTimeoutMs: this.timeoutMs,
      maxResponseBytes: 1 << 20,
    }, context.cancellation);
    return normalizePlatformToolResult(call.id, response);
  }

  private resolveServerContext(sessionId: string): Record<string, unknown> {
    if (!this.serverContext) return {};
    const raw = host.secretGet(sessionId, this.serverContext.secretRef);
    if (!raw) throw platformToolBindingError("Platform tool integration credential is unavailable");
    let value: unknown;
    try {
      value = JSON.parse(raw) as unknown;
    } catch {
      throw platformToolBindingError("Platform tool integration credential is invalid");
    }
    if (!isRecord(value)) throw platformToolBindingError("Platform tool integration credential is invalid");
    const accessToken = boundedSecret(value.access_token, 4_096);
    const mode = value.mode === undefined ? "" : boundedSecret(value.mode, 128);
    if (!accessToken || (value.mode !== undefined && mode !== "guest")) {
      throw platformToolBindingError("Platform tool integration credential is invalid");
    }
    return {
      server_context: {
        netease_music: {
          access_token: accessToken,
          ...(mode ? { mode } : {}),
        },
      },
    };
  }
}

export interface CustomHTTPToolExecutorOptions {
  url: string;
  headers?: Record<string, string>;
  secretHeadersRef?: string;
  responseMapper?: (response: unknown, call: ToolCall) => unknown;
  timeoutMs?: number;
  maxResponseBytes?: number;
  allowInsecureHttp?: boolean;
}

const CUSTOM_TOOL_PROTECTED_HEADERS = new Set([
  "host",
  "content-length",
  "connection",
  "x-agent-session-id",
  "x-agent-turn-id",
  "x-agent-tool-call-id",
  "x-request-id",
  "idempotency-key",
]);

export class CustomHTTPToolExecutor implements ToolExecutor {
  private readonly url: string;
  private readonly headers: Array<[string, string]>;
  private readonly secretHeadersRef?: string;
  private readonly responseMapper?: CustomHTTPToolExecutorOptions["responseMapper"];
  private readonly timeoutMs?: number;
  private readonly maxResponseBytes: number;

  constructor(options: CustomHTTPToolExecutorOptions) {
    const allowedScheme = options.allowInsecureHttp ? /^https?:\/\//i : /^https:\/\//i;
    if (!allowedScheme.test(options.url)) {
      throw new AgentError("AGENT_TOOL_BINDING_INVALID", "Custom tool URL is not allowed", {
        phase: "tool",
      });
    }
    this.url = options.url;
    this.headers = validateCustomHeaders(options.headers ?? {});
    this.secretHeadersRef = options.secretHeadersRef;
    this.responseMapper = options.responseMapper;
    this.timeoutMs = options.timeoutMs;
    this.maxResponseBytes = Math.min(options.maxResponseBytes ?? 1 << 20, 8 << 20);
  }

  execute(call: ToolCall, context: ToolExecutionContext): Promise<ToolResult> {
    context.cancellation.throwIfCancelled();
    const headers: Array<[string, string]> = [
      ["Accept", "application/json"],
      ["Content-Type", "application/json"],
      ...this.headers,
      ...this.secretHeaders(context.sessionId),
    ];
    return new Promise((resolve, reject) => {
      let streamId = "";
      let status = 0;
      let contentType = "";
      let settled = false;
      let totalBytes = 0;
      const chunks: Uint8Array[] = [];
      let unsubscribe: () => void = () => undefined;
      const cleanup = (): void => unsubscribe();
      const rejectOnce = (error: AgentError, cancel = false): void => {
        if (settled) return;
        settled = true;
        if (cancel && streamId) host.httpStreamCancel(streamId);
        cleanup();
        reject(error);
      };
      const handlers: HTTPStreamHandlers = {
        onHeaders(value, responseHeaders): void {
          status = value;
          for (const [name, headerValue] of responseHeaders) {
            if (name.toLowerCase() === "content-type") contentType = headerValue;
          }
        },
        onChunk: (chunk) => {
          totalBytes += chunk.length;
          if (totalBytes > this.maxResponseBytes) {
            rejectOnce(customToolError("Custom tool response is too large"), true);
            return;
          }
          chunks.push(chunk);
        },
        onDone: () => {
          if (settled) return;
          if (status < 200 || status >= 300) {
            rejectOnce(customToolError("Custom tool request failed"));
            return;
          }
          if (!isJSONMediaType(contentType)) {
            rejectOnce(customToolError("Custom tool returned a non-JSON response"));
            return;
          }
          let decoded: unknown;
          try {
            decoded = JSON.parse(decodeUTF8(joinChunks(chunks, totalBytes))) as unknown;
          } catch (error) {
            rejectOnce(customToolError("Custom tool returned invalid JSON", error));
            return;
          }
          try {
            const mapped = this.responseMapper ? this.responseMapper(decoded, call) : decoded;
            const result = normalizePlatformToolResult(call.id, mapped);
            settled = true;
            cleanup();
            resolve(result);
          } catch (error) {
            rejectOnce(error instanceof AgentError ? error : customToolError("Invalid custom tool response", error));
          }
        },
        onError: (error) => rejectOnce(new AgentError(
          "AGENT_CUSTOM_TOOL_ERROR",
          "Custom tool request failed",
          { retryable: error.retryable, phase: "tool" },
        )),
      };
      const request: HTTPStreamRequest = {
        method: "POST",
        url: this.url,
        headers,
        body: encodeUTF8(JSON.stringify(call.parsedArguments)),
        responseMode: "buffer",
        totalTimeoutMs: this.timeoutMs,
        maxResponseBytes: this.maxResponseBytes,
      };
      streamId = host.httpStreamStart(request, handlers);
      unsubscribe = context.cancellation.onCancel((reason) => {
        rejectOnce(new AgentError("AGENT_CANCELLED", reason || "Custom tool cancelled", {
          phase: "tool",
        }), true);
      });
    });
  }

  private secretHeaders(sessionId: string): Array<[string, string]> {
    if (!this.secretHeadersRef) return [];
    const raw = host.secretGet(sessionId, this.secretHeadersRef);
    if (!raw) throw new AgentError("AGENT_TOOL_BINDING_INVALID", "Custom tool credentials are unavailable", {
      phase: "tool",
    });
    let decoded: unknown;
    try {
      decoded = JSON.parse(raw) as unknown;
    } catch {
      throw new AgentError("AGENT_TOOL_BINDING_INVALID", "Custom tool headers are invalid", {
        phase: "tool",
      });
    }
    if (!isRecord(decoded)) throw new AgentError("AGENT_TOOL_BINDING_INVALID", "Custom tool headers are invalid", { phase: "tool" });
    const headers: Array<[string, string]> = [];
    for (const [name, value] of Object.entries(decoded)) {
      if (CUSTOM_TOOL_PROTECTED_HEADERS.has(name.toLowerCase()) || typeof value !== "string" || /[\r\n]/.test(name + value)) {
        throw new AgentError("AGENT_TOOL_BINDING_INVALID", `Custom tool header ${name} is not allowed`, {
          phase: "tool",
        });
      }
      headers.push([name, value]);
    }
    return headers;
  }
}

function joinChunks(chunks: Uint8Array[], totalBytes: number): Uint8Array {
  if (chunks.length === 1) return chunks[0];
  const bytes = new Uint8Array(totalBytes);
  let offset = 0;
  for (const chunk of chunks) {
    bytes.set(chunk, offset);
    offset += chunk.length;
  }
  return bytes;
}

function validateCustomHeaders(value: Record<string, string>): Array<[string, string]> {
  const headers: Array<[string, string]> = [];
  for (const [name, headerValue] of Object.entries(value)) {
    if (CUSTOM_TOOL_PROTECTED_HEADERS.has(name.toLowerCase())
      || typeof headerValue !== "string"
      || /[\r\n]/.test(name + headerValue)) {
      throw new AgentError("AGENT_TOOL_BINDING_INVALID", `Custom tool header ${name} is not allowed`, {
        phase: "tool",
      });
    }
    headers.push([name, headerValue]);
  }
  return headers;
}

function normalizePlatformToolResult(callId: string, value: unknown): ToolResult {
  const hasCallId = isRecord(value) && Object.prototype.hasOwnProperty.call(value, "callId");
  const normalized = normalizeClosedToolResult(value, callId, hasCallId);
  if (!normalized) {
    throw new AgentError("AGENT_TOOL_PROTOCOL_ERROR", "Invalid platform tool response", {
      phase: "tool",
    });
  }
  return normalized;
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function customToolError(message: string, _cause?: unknown): AgentError {
  return new AgentError("AGENT_CUSTOM_TOOL_ERROR", message, {
    retryable: true,
    phase: "tool",
  });
}

function isJSONMediaType(contentType: string): boolean {
  const mediaType = contentType.split(";", 1)[0].trim().toLowerCase();
  return mediaType === "application/json"
    || (mediaType.startsWith("application/") && mediaType.endsWith("+json"));
}

function platformToolBindingError(message: string): AgentError {
  return new AgentError("AGENT_TOOL_BINDING_INVALID", message, { phase: "tool" });
}

function boundedSecret(value: unknown, maxLength: number): string {
  return typeof value === "string"
    && value.length > 0
    && value.length <= maxLength
    && !/[\u0000-\u001f\u007f]/.test(value)
    ? value
    : "";
}

function boundedToolTimeout(value?: number): number {
  if (!Number.isFinite(value) || Number(value) <= 0) return 30_000;
  return Math.min(Math.floor(Number(value)), 120_000);
}
