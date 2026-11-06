import type { HTTPStreamHandlers, HTTPStreamRequest } from "../host";
import { encodeUTF8 } from "../http/utf8";
import { decodeUTF8 } from "../http/utf8";
import { parseAbsoluteHTTPURL } from "../http/url";
import type { CancellationToken } from "../runtime/cancellation";
import { AgentError, sanitizePublicErrorDetails } from "../runtime/errors";

export interface AgentRuntimeRequestContext {
  sessionId: string;
  turnId?: string;
  requestId: string;
  toolCallId?: string;
  appId?: string;
}

export interface AgentRuntimeTransportOptions {
  baseUrl: string;
  tokenSecretKey: string;
}

export interface AgentRuntimeStreamRequest {
  path: string;
  method?: string;
  body?: unknown;
  responseMode?: "stream" | "buffer";
  context: AgentRuntimeRequestContext;
  connectTimeoutMs?: number;
  firstByteTimeoutMs?: number;
  idleTimeoutMs?: number;
  totalTimeoutMs?: number;
  maxResponseBytes?: number;
}

export interface HTTPRunHandle {
  id: string;
  cancel(reason?: string): void;
}

export interface AgentRuntimeJSONResponse<T> {
  status: number;
  body?: T;
}

/** Injects auth and correlation only for LLMRequestService Agent Runtime calls. */
export class AgentRuntimeTransport {
  private readonly baseUrl: string;
  private readonly tokenSecretKey: string;

  constructor(options: AgentRuntimeTransportOptions) {
    this.baseUrl = normalizeAgentRuntimeBase(options.baseUrl);
    this.tokenSecretKey = options.tokenSecretKey;
  }

  stream(
    request: AgentRuntimeStreamRequest,
    handlers: HTTPStreamHandlers,
    cancellation: CancellationToken,
  ): HTTPRunHandle {
    cancellation.throwIfCancelled();
    validateCorrelation(request.context);
    const token = host.secretGet(request.context.sessionId, this.tokenSecretKey);
    if (!token) {
      throw new AgentError("AGENT_UNAUTHENTICATED", "Agent authentication is unavailable", {
        phase: "transport",
      });
    }
    if (!request.path.startsWith("/") || request.path.includes("..")) {
      throw new AgentError("AGENT_REQUEST_INVALID", "Invalid Agent Runtime path", {
        phase: "transport",
      });
    }

    const headers: Array<[string, string]> = [
      ["Authorization", `Bearer ${token}`],
      ["Accept", "text/event-stream, application/json"],
      ["Content-Type", "application/json"],
      ["X-Agent-Session-Id", request.context.sessionId],
      ["X-Request-Id", request.context.requestId],
    ];
    if (request.context.appId) headers.push(["X-Agent-App-Id", request.context.appId]);
    if (request.context.turnId) headers.push(["X-Agent-Turn-Id", request.context.turnId]);
    if (request.context.toolCallId) headers.push(["X-Agent-Tool-Call-Id", request.context.toolCallId]);

    let terminal = false;
    let streamId = "";
    let unsubscribe: () => void = () => undefined;
    const cleanup = (): void => {
      if (terminal) return;
      terminal = true;
      unsubscribe();
    };
    const wrapped: HTTPStreamHandlers = {
      onHeaders: handlers.onHeaders,
      onChunk: handlers.onChunk,
      onDone: () => {
        if (terminal) return;
        cleanup();
        handlers.onDone?.();
      },
      onError: (error) => {
        if (terminal) return;
        cleanup();
        handlers.onError?.(error);
      },
    };
    const hostRequest: HTTPStreamRequest = {
      method: request.method ?? "POST",
      url: this.baseUrl + request.path,
      headers,
      body: request.body === undefined ? null : encodeUTF8(JSON.stringify(request.body)),
      responseMode: request.responseMode,
      connectTimeoutMs: request.connectTimeoutMs,
      firstByteTimeoutMs: request.firstByteTimeoutMs,
      idleTimeoutMs: request.idleTimeoutMs,
      totalTimeoutMs: request.totalTimeoutMs,
      maxResponseBytes: request.maxResponseBytes,
    };
    streamId = host.httpStreamStart(hostRequest, wrapped);
    const cancel = (reason?: string): void => {
      if (terminal) return;
      cleanup();
      host.httpStreamCancel(streamId);
      handlers.onError?.({
        code: "AGENT_CANCELLED",
        message: reason || "Agent operation cancelled",
        retryable: false,
      });
    };
    unsubscribe = cancellation.onCancel(cancel);
    return { id: streamId, cancel };
  }

  requestJSON<T>(
    request: AgentRuntimeStreamRequest,
    cancellation: CancellationToken,
  ): Promise<T> {
    return this.requestJSONResponse<T>(request, cancellation).then((response) => {
      if (response.body === undefined) {
        throw new AgentError("AGENT_RESPONSE_INVALID", "Agent Runtime returned an empty JSON response", {
          phase: "transport",
        });
      }
      return response.body;
    });
  }

  requestJSONResponse<T>(
    request: AgentRuntimeStreamRequest,
    cancellation: CancellationToken,
  ): Promise<AgentRuntimeJSONResponse<T>> {
    return new Promise<AgentRuntimeJSONResponse<T>>((resolve, reject) => {
      const startedAt = Date.now();
      const requestMethod = request.method ?? "POST";
      let requestLogged = false;
      const logRequest = (
        outcome: "success" | "error",
        metrics: {
          status: number;
          durationMs: number;
          responseBytes: number;
          transportDurationMs?: number;
          decodeDurationMs?: number;
        },
        errorCode?: string,
      ): void => {
        if (requestLogged || request.path === "/model/chat/completions") return;
        requestLogged = true;
        try {
          if (typeof host === "undefined" || typeof host.log !== "function") return;
          host.log("info", "agent runtime request completed", {
            origin: "agent",
            event: "agent_runtime.request.completed",
            method: requestMethod,
            path: request.path,
            sessionId: request.context.sessionId,
            ...(request.context.turnId ? { turnId: request.context.turnId } : {}),
            requestId: request.context.requestId,
            ...(request.context.toolCallId ? { toolCallId: request.context.toolCallId } : {}),
            ...(metrics.status > 0 ? { status: metrics.status } : {}),
            durationMs: metrics.durationMs,
            responseBytes: metrics.responseBytes,
            ...(metrics.transportDurationMs !== undefined
              ? { transportDurationMs: metrics.transportDurationMs }
              : {}),
            ...(metrics.decodeDurationMs !== undefined
              ? { decodeDurationMs: metrics.decodeDurationMs }
              : {}),
            outcome,
            ...(errorCode ? { errorCode } : {}),
          });
        } catch {
          // Observability must never change Runtime request behavior.
        }
      };
      let status = 0;
      const chunks: Uint8Array[] = [];
      let responseBytes = 0;
      let settled = false;
      let handle: HTTPRunHandle | undefined;
      const deferRequestLog = (
        outcome: "success" | "error",
        errorCode?: string,
        details: { transportDurationMs?: number; decodeDurationMs?: number } = {},
      ): void => {
        const metrics = {
          status,
          durationMs: Math.max(0, Date.now() - startedAt),
          responseBytes,
          ...details,
        };
        deferHostLog(() => logRequest(outcome, metrics, errorCode));
      };
      const rejectOnce = (
        error: AgentError,
        cancelTransport = false,
        details: { transportDurationMs?: number; decodeDurationMs?: number } = {},
      ): void => {
        if (settled) return;
        settled = true;
        if (cancelTransport) handle?.cancel(error.message);
        deferRequestLog("error", error.code, details);
        reject(error);
      };
      try {
        handle = this.stream({ ...request, responseMode: "buffer" }, {
          onHeaders(value): void {
            status = value;
          },
          onChunk(chunk): void {
            if (settled) return;
            responseBytes += chunk.length;
            if (responseBytes > (request.maxResponseBytes ?? 1 << 20)) {
              rejectOnce(new AgentError("AGENT_RESPONSE_TOO_LARGE", "Agent Runtime response is too large", {
                phase: "transport",
              }), true);
              return;
            }
            chunks.push(chunk);
          },
          onDone(): void {
            if (settled) return;
            const transportDurationMs = Math.max(0, Date.now() - startedAt);
            const decodeStartedAt = Date.now();
            let decoded: unknown = undefined;
            if (responseBytes > 0) {
              try {
                const bytes = joinChunks(chunks, responseBytes);
                decoded = JSON.parse(decodeUTF8(bytes)) as unknown;
              } catch (error) {
                rejectOnce(new AgentError("AGENT_RESPONSE_INVALID", "Agent Runtime returned invalid JSON", {
                  phase: "transport",
                }), false, {
                  transportDurationMs,
                  decodeDurationMs: Math.max(0, Date.now() - decodeStartedAt),
                });
                return;
              }
            }
            const decodeDurationMs = Math.max(0, Date.now() - decodeStartedAt);
            if ((status < 200 || status >= 300) && status !== 304) {
              rejectOnce(agentRuntimeHTTPError(status, decoded), false, {
                transportDurationMs,
                decodeDurationMs,
              });
              return;
            }
            settled = true;
            resolve({ status, body: decoded as T | undefined });
            deferRequestLog("success", undefined, { transportDurationMs, decodeDurationMs });
          },
          onError(error): void {
            rejectOnce(new AgentError(error.code, error.message, {
              retryable: error.retryable,
              phase: "transport",
            }));
          },
        }, cancellation);
      } catch (error) {
        const normalized = error instanceof AgentError
          ? error
          : new AgentError("AGENT_UPSTREAM_ERROR", "Agent Runtime request failed", {
            phase: "transport",
            retryable: true,
          });
        rejectOnce(normalized);
      }
    });
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

/** Keep diagnostic host IPC off the Runtime request completion path. */
function deferHostLog(callback: () => void): void {
  const run = (): void => {
    try {
      callback();
    } catch {
      // Observability must never change Runtime request behavior.
    }
  };
  try {
    if (typeof host !== "undefined" && typeof host.timerStart === "function") {
      host.timerStart(1, run);
      return;
    }
  } catch {
    // Fall through to the inline fallback for lightweight test hosts.
  }
  // Lightweight test hosts do not always expose timers. Run inline there so
  // a later session cannot observe a stale completion log.
  run();
}

function normalizeAgentRuntimeBase(value: string): string {
  const parsed = parseAbsoluteHTTPURL(value);
  if (!parsed) {
    throw new AgentError("AGENT_MODEL_CONFIG_INVALID", "Platform base URL must use HTTPS", {
      phase: "config",
    });
  }
  const base = `${parsed.scheme}://${parsed.authority}${parsed.path.replace(/\/+$/, "")}`;
  if (base.endsWith("/v1/agent-runtime")) return base;
  if (base.endsWith("/v1")) return `${base}/agent-runtime`;
  return `${base}/v1/agent-runtime`;
}

function validateCorrelation(context: AgentRuntimeRequestContext): void {
  for (const [name, value, required] of [
    ["sessionId", context.sessionId, true],
    ["turnId", context.turnId, false],
    ["requestId", context.requestId, true],
    ["toolCallId", context.toolCallId, false],
  ] as Array<[string, string | undefined, boolean]>) {
    if (!value && !required) continue;
    if (!value || value.length > 128 || !/^[A-Za-z0-9._:-]+$/.test(value)) {
      throw new AgentError("AGENT_REQUEST_INVALID", `Invalid ${name}`, { phase: "transport" });
    }
  }
	if (context.turnId && !/^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i.test(context.turnId)) {
		throw new AgentError("AGENT_REQUEST_INVALID", "Invalid turnId", { phase: "transport" });
	}
}

function agentRuntimeHTTPError(status: number, decoded: unknown): AgentError {
  const body = isRecord(decoded) ? decoded : {};
  const code = typeof body.code === "string"
    ? body.code
    : status === 429
      ? "AGENT_CAPABILITY_QUOTA_EXCEEDED"
      : status >= 500
        ? "AGENT_UPSTREAM_ERROR"
        : "AGENT_REQUEST_INVALID";
  const message = typeof body.message === "string" ? body.message : "Agent Runtime request failed";
  return new AgentError(code, message, {
    retryable: status >= 500,
    phase: "transport",
    publicDetails: sanitizePublicErrorDetails(body.details),
  });
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}
