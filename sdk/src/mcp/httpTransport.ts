import type { HTTPStreamHandlers, HTTPStreamRequest } from "../host";
import { decodeUTF8, encodeUTF8 } from "../http/utf8";
import type { CancellationToken } from "../runtime/cancellation";
import { AgentError } from "../runtime/errors";
import type { JSONRPCRequest, MCPTransport } from "./client";

export interface HostMCPHTTPTransportOptions {
  sessionId: string;
  transport?: "streamable_http" | "sse";
  url: string;
  secretHeadersRef?: string;
  timeoutMs?: number;
  maxResponseBytes?: number;
  allowInsecureHttp?: boolean;
}

interface PendingSSECall {
  resolve(value: unknown): void;
  reject(error: AgentError): void;
  unsubscribe(): void;
  timerId?: string;
}

const DEFAULT_MCP_REQUEST_TIMEOUT_MS = 30_000;
const MAX_MCP_REQUEST_TIMEOUT_MS = 120_000;

const PROTECTED_HEADERS = new Set([
  "host",
  "content-length",
  "connection",
  "mcp-session-id",
  "x-agent-session-id",
  "x-agent-turn-id",
  "x-agent-tool-call-id",
  "x-request-id",
  "idempotency-key",
]);

export class HostMCPHTTPTransport implements MCPTransport {
  private readonly sessionId: string;
  private readonly transport: "streamable_http" | "sse";
  private readonly url: string;
  private readonly secretHeadersRef?: string;
  private readonly timeoutMs: number;
  private readonly maxResponseBytes: number;
  private readonly active = new Set<string>();
  private readonly activeFailures = new Map<string, (error: AgentError) => void>();
  private mcpSessionId?: string;
  private closed = false;
  private sseEndpoint?: string;
  private sseConnect?: Promise<void>;
  private sseConnectResolve?: () => void;
  private sseConnectReject?: (error: AgentError) => void;
  private sseConnectTimerId?: string;
  private readonly sseBytes: number[] = [];
  private readonly pendingSSE = new Map<string, PendingSSECall>();

  constructor(options: HostMCPHTTPTransportOptions) {
    const allowedScheme = options.allowInsecureHttp ? /^https?:\/\//i : /^https:\/\//i;
    if (!allowedScheme.test(options.url)) {
      throw new AgentError("AGENT_MCP_CONFIG_INVALID", "MCP URL is not allowed", { phase: "mcp" });
    }
    this.sessionId = options.sessionId;
    this.transport = options.transport ?? "streamable_http";
    this.url = options.url;
    this.secretHeadersRef = options.secretHeadersRef;
    this.timeoutMs = boundedMCPTimeout(options.timeoutMs);
    this.maxResponseBytes = Math.min(options.maxResponseBytes ?? 1 << 20, 8 << 20);
  }

  request(request: JSONRPCRequest, cancellation: CancellationToken): Promise<unknown> {
    if (this.transport === "sse") return this.requestSSE(request, cancellation);
    return this.requestStreamable(request, cancellation);
  }

  private requestStreamable(request: JSONRPCRequest, cancellation: CancellationToken): Promise<unknown> {
    if (this.closed) return Promise.reject(mcpTransportError("MCP transport is closed"));
    cancellation.throwIfCancelled();
    const headers: Array<[string, string]> = [
      ["Accept", "application/json, text/event-stream"],
      ["Content-Type", "application/json"],
      ...this.secretHeaders(),
    ];
    if (this.mcpSessionId) headers.push(["Mcp-Session-Id", this.mcpSessionId]);
    return new Promise((resolve, reject) => {
      let streamId = "";
      let status = 0;
      let contentType = "";
      const bytes: number[] = [];
      let settled = false;
      let unsubscribe: () => void = () => undefined;
      const cleanup = (): void => {
        if (streamId) {
          this.active.delete(streamId);
          this.activeFailures.delete(streamId);
        }
        unsubscribe();
      };
      const rejectOnce = (error: AgentError, cancel = false): void => {
        if (settled) return;
        settled = true;
        if (cancel && streamId) host.httpStreamCancel(streamId);
        cleanup();
        reject(error);
      };
      const handlers: HTTPStreamHandlers = {
        onHeaders: (value, responseHeaders) => {
          status = value;
          for (const [name, headerValue] of responseHeaders) {
            if (name.toLowerCase() === "content-type") contentType = headerValue.toLowerCase();
            if (name.toLowerCase() === "mcp-session-id" && headerValue) this.mcpSessionId = headerValue;
          }
        },
        onChunk: (chunk) => {
          if (bytes.length + chunk.length > this.maxResponseBytes) {
            rejectOnce(mcpTransportError("MCP response is too large"), true);
            return;
          }
          bytes.push(...Array.from(chunk));
        },
        onDone: () => {
          if (settled) return;
          if (status === 202 && bytes.length === 0) {
            settled = true;
            cleanup();
            resolve(undefined);
            return;
          }
          let decoded: unknown;
          try {
            const text = decodeUTF8(new Uint8Array(bytes));
            decoded = contentType.includes("text/event-stream")
              ? decodeJSONRPCSSE(text, request.id)
              : JSON.parse(text);
          } catch (error) {
            rejectOnce(mcpTransportError("Invalid MCP response", error));
            return;
          }
          if (status < 200 || status >= 300) {
            rejectOnce(mcpTransportError("MCP request failed"));
            return;
          }
          settled = true;
          cleanup();
          resolve(decoded);
        },
        onError: () => rejectOnce(mcpTransportError("MCP request failed")),
      };
      const hostRequest: HTTPStreamRequest = {
        method: "POST",
        url: this.url,
        headers,
        body: encodeUTF8(JSON.stringify(request)),
        totalTimeoutMs: this.timeoutMs,
        maxResponseBytes: this.maxResponseBytes,
      };
      streamId = host.httpStreamStart(hostRequest, handlers);
      this.active.add(streamId);
      this.activeFailures.set(streamId, (error) => rejectOnce(error));
      unsubscribe = cancellation.onCancel((reason) => {
        rejectOnce(new AgentError("AGENT_CANCELLED", reason || "MCP request cancelled", {
          phase: "mcp",
        }), true);
      });
    });
  }

  private async requestSSE(request: JSONRPCRequest, cancellation: CancellationToken): Promise<unknown> {
    if (this.closed) throw mcpTransportError("MCP transport is closed");
    cancellation.throwIfCancelled();
    await cancellable(this.ensureSSEConnection(), cancellation);
    const endpoint = this.sseEndpoint;
    if (!endpoint) throw mcpTransportError("MCP SSE endpoint is unavailable");
    if (request.id === undefined) {
      await this.postSSE(endpoint, request, cancellation);
      return undefined;
    }

    const id = String(request.id);
    if (this.pendingSSE.has(id)) throw mcpTransportError("Duplicate MCP request ID");
    return new Promise((resolve, reject) => {
      const pending: PendingSSECall = {
        resolve,
        reject,
        unsubscribe: () => undefined,
      };
      pending.unsubscribe = cancellation.onCancel((reason) => {
        const current = this.takeSSEPending(id);
        current?.reject(new AgentError("AGENT_CANCELLED", reason || "MCP request cancelled", {
          phase: "mcp",
        }));
      });
      pending.timerId = host.timerStart(this.timeoutMs, () => {
        this.failSSE(mcpTransportError("MCP SSE request timed out"));
      });
      this.pendingSSE.set(id, pending);
      this.postSSE(endpoint, request, cancellation).then((response) => {
        if (response === undefined) return;
        this.takeSSEPending(id)?.resolve(response);
      }, (error: unknown) => {
        const normalized = error instanceof AgentError
          ? error
          : mcpTransportError("MCP SSE POST failed", error);
        if (normalized.code === "AGENT_CANCELLED") {
          this.takeSSEPending(id)?.reject(normalized);
          return;
        }
        this.failSSE(normalized);
      });
    });
  }

  private ensureSSEConnection(): Promise<void> {
    if (this.sseEndpoint) return Promise.resolve();
    if (this.sseConnect) return this.sseConnect;
    this.sseConnect = new Promise<void>((resolve, reject) => {
      this.sseConnectResolve = resolve;
      this.sseConnectReject = reject;
    });
    const headers: Array<[string, string]> = [
      ["Accept", "text/event-stream"],
      ...this.secretHeaders(),
    ];
    let streamId = "";
    const handlers: HTTPStreamHandlers = {
      onHeaders: (status) => {
        if (status < 200 || status >= 300) {
          this.failSSE(mcpTransportError(`MCP SSE connection failed with status ${status}`));
        }
      },
      onChunk: (chunk) => this.consumeSSEChunk(chunk),
      onDone: () => {
        if (!this.closed) this.failSSE(mcpTransportError("MCP SSE connection closed"));
      },
      onError: () => this.failSSE(mcpTransportError("MCP connection failed")),
    };
    streamId = host.httpStreamStart({
      method: "GET",
      url: this.url,
      headers,
      body: null,
      idleTimeoutMs: this.timeoutMs,
      maxResponseBytes: this.maxResponseBytes,
    }, handlers);
    if (this.closed) {
      host.httpStreamCancel(streamId);
      return this.sseConnect;
    }
    this.active.add(streamId);
    if (!this.sseEndpoint) {
      try {
        this.sseConnectTimerId = host.timerStart(this.timeoutMs, () => {
          this.failSSE(mcpTransportError("MCP SSE endpoint timed out"));
        });
      } catch (error) {
        this.failSSE(mcpTransportError("MCP SSE endpoint timer failed", error));
      }
    }
    return this.sseConnect;
  }

  private postSSE(
    endpoint: string,
    request: JSONRPCRequest,
    cancellation: CancellationToken,
  ): Promise<unknown> {
    return new Promise((resolve, reject) => {
      let streamId = "";
      let status = 0;
      const bytes: number[] = [];
      let settled = false;
      let unsubscribe: () => void = () => undefined;
      const cleanup = (): void => {
        if (streamId) {
          this.active.delete(streamId);
          this.activeFailures.delete(streamId);
        }
        unsubscribe();
      };
      const rejectOnce = (error: AgentError, cancel = false): void => {
        if (settled) return;
        settled = true;
        if (cancel && streamId) host.httpStreamCancel(streamId);
        cleanup();
        reject(error);
      };
      const handlers: HTTPStreamHandlers = {
        onHeaders: (value) => { status = value; },
        onChunk: (chunk) => {
          if (bytes.length + chunk.length > this.maxResponseBytes) {
            rejectOnce(mcpTransportError("MCP SSE POST response is too large"), true);
            return;
          }
          bytes.push(...Array.from(chunk));
        },
        onDone: () => {
          if (settled) return;
          if (status < 200 || status >= 300) {
            rejectOnce(mcpTransportError(`MCP SSE POST failed with status ${status}`));
            return;
          }
          let decoded: unknown = undefined;
          if (bytes.length > 0) {
            try {
              decoded = JSON.parse(decodeUTF8(new Uint8Array(bytes))) as unknown;
            } catch (error) {
              rejectOnce(mcpTransportError("Invalid MCP SSE POST response", error));
              return;
            }
          }
          settled = true;
          cleanup();
          resolve(decoded);
        },
        onError: () => rejectOnce(mcpTransportError("MCP request failed")),
      };
      streamId = host.httpStreamStart({
        method: "POST",
        url: endpoint,
        headers: [
          ["Accept", "application/json"],
          ["Content-Type", "application/json"],
          ...this.secretHeaders(),
        ],
        body: encodeUTF8(JSON.stringify(request)),
        totalTimeoutMs: this.timeoutMs,
        maxResponseBytes: this.maxResponseBytes,
      }, handlers);
      this.active.add(streamId);
      this.activeFailures.set(streamId, (error) => rejectOnce(error));
      unsubscribe = cancellation.onCancel((reason) => {
        rejectOnce(new AgentError("AGENT_CANCELLED", reason || "MCP request cancelled", {
          phase: "mcp",
        }), true);
      });
    });
  }

  private consumeSSEChunk(chunk: Uint8Array): void {
    if (this.closed) return;
    if (this.sseBytes.length + chunk.length > this.maxResponseBytes) {
      this.failSSE(mcpTransportError("MCP SSE event buffer is too large"));
      return;
    }
    this.sseBytes.push(...Array.from(chunk));
    while (true) {
      const boundary = sseFrameBoundary(this.sseBytes);
      if (!boundary) return;
      const frame = this.sseBytes.splice(0, boundary.consumed).slice(0, boundary.frameBytes);
      try {
        this.consumeSSEFrame(decodeUTF8(new Uint8Array(frame)));
      } catch (error) {
        this.failSSE(mcpTransportError("Invalid MCP SSE event", error));
        return;
      }
    }
  }

  private consumeSSEFrame(frame: string): void {
    const parsed = parseSSEFrame(frame);
    if (!parsed) return;
    if (parsed.event === "endpoint") {
      if (this.sseEndpoint) return;
      this.sseEndpoint = resolveSameOriginEndpoint(this.url, parsed.data);
      this.clearSSEConnectTimer();
      this.sseConnectResolve?.();
      this.sseConnectResolve = undefined;
      this.sseConnectReject = undefined;
      return;
    }
    if (parsed.event !== "message" && parsed.event !== "") return;
    const response = JSON.parse(parsed.data) as unknown;
    if (!isRecord(response) || response.id === undefined) return;
    this.takeSSEPending(String(response.id))?.resolve(response);
  }

  private takeSSEPending(id: string): PendingSSECall | undefined {
    const pending = this.pendingSSE.get(id);
    if (!pending) return undefined;
    this.pendingSSE.delete(id);
    pending.unsubscribe();
    if (pending.timerId) host.timerCancel(pending.timerId);
    return pending;
  }

  private failSSE(error: AgentError): void {
    if (this.closed) return;
    this.closed = true;
    this.clearSSEConnectTimer();
    this.sseConnectReject?.(error);
    this.sseConnectResolve = undefined;
    this.sseConnectReject = undefined;
    for (const id of Array.from(this.pendingSSE.keys())) {
      this.takeSSEPending(id)?.reject(error);
    }
    const active = Array.from(this.active);
    for (const reject of Array.from(this.activeFailures.values())) reject(error);
    for (const streamId of active) host.httpStreamCancel(streamId);
    this.active.clear();
    this.activeFailures.clear();
  }

  private clearSSEConnectTimer(): void {
    if (!this.sseConnectTimerId) return;
    const timerId = this.sseConnectTimerId;
    this.sseConnectTimerId = undefined;
    host.timerCancel(timerId);
  }

  close(): void {
    if (this.closed) return;
    this.failSSE(mcpTransportError("MCP transport is closed"));
  }

  private secretHeaders(): Array<[string, string]> {
    if (!this.secretHeadersRef) return [];
    const raw = host.secretGet(this.sessionId, this.secretHeadersRef);
    if (!raw) throw new AgentError("AGENT_MCP_CONFIG_INVALID", "MCP credentials are unavailable", {
      phase: "mcp",
    });
    let decoded: unknown;
    try {
      decoded = JSON.parse(raw) as unknown;
    } catch {
      throw new AgentError("AGENT_MCP_CONFIG_INVALID", "MCP credential headers are invalid", {
        phase: "mcp",
      });
    }
    if (!isRecord(decoded)) throw new AgentError("AGENT_MCP_CONFIG_INVALID", "MCP credential headers are invalid", { phase: "mcp" });
    const headers: Array<[string, string]> = [];
    for (const [name, value] of Object.entries(decoded)) {
      if (PROTECTED_HEADERS.has(name.toLowerCase()) || typeof value !== "string" || /[\r\n]/.test(name + value)) {
        throw new AgentError("AGENT_MCP_CONFIG_INVALID", `MCP header ${name} is not allowed`, {
          phase: "mcp",
        });
      }
      headers.push([name, value]);
    }
    return headers;
  }
}

function cancellable<T>(promise: Promise<T>, cancellation: CancellationToken): Promise<T> {
  return new Promise((resolve, reject) => {
    let settled = false;
    const unsubscribe = cancellation.onCancel((reason) => {
      if (settled) return;
      settled = true;
      reject(new AgentError("AGENT_CANCELLED", reason || "MCP request cancelled", { phase: "mcp" }));
    });
    promise.then((value) => {
      if (settled) return;
      settled = true;
      unsubscribe();
      resolve(value);
    }, (error: unknown) => {
      if (settled) return;
      settled = true;
      unsubscribe();
      reject(error);
    });
  });
}

function sseFrameBoundary(bytes: number[]): { frameBytes: number; consumed: number } | undefined {
  for (let index = 0; index < bytes.length - 1; index += 1) {
    if (bytes[index] === 0x0a && bytes[index + 1] === 0x0a) {
      return { frameBytes: index, consumed: index + 2 };
    }
    if (index + 3 < bytes.length
      && bytes[index] === 0x0d
      && bytes[index + 1] === 0x0a
      && bytes[index + 2] === 0x0d
      && bytes[index + 3] === 0x0a) {
      return { frameBytes: index, consumed: index + 4 };
    }
  }
  return undefined;
}

function parseSSEFrame(frame: string): { event: string; data: string } | undefined {
  let event = "";
  const data: string[] = [];
  for (const rawLine of frame.replace(/\r\n/g, "\n").split("\n")) {
    if (!rawLine || rawLine.startsWith(":")) continue;
    const separator = rawLine.indexOf(":");
    const field = separator < 0 ? rawLine : rawLine.slice(0, separator);
    const value = separator < 0 ? "" : rawLine.slice(separator + 1).replace(/^ /, "");
    if (field === "event") event = value;
    if (field === "data") data.push(value);
  }
  if (data.length === 0) return undefined;
  return { event, data: data.join("\n") };
}

function resolveSameOriginEndpoint(sourceURL: string, endpoint: string): string {
  const source = /^(https?:\/\/[^/]+)(\/.*)?$/i.exec(sourceURL);
  if (!source || /[\r\n]/.test(endpoint)) throw new Error("Invalid MCP SSE endpoint");
  const origin = source[1];
  if (endpoint.startsWith("/")) return origin + endpoint;
  if (/^https?:\/\//i.test(endpoint)) {
    const target = /^(https?:\/\/[^/]+)(\/.*)?$/i.exec(endpoint);
    if (!target || target[1].toLowerCase() !== origin.toLowerCase()) {
      throw new Error("Cross-origin MCP SSE endpoint is forbidden");
    }
    return endpoint;
  }
  const path = source[2] ?? "/";
  const directory = path.slice(0, path.lastIndexOf("/") + 1);
  return origin + directory + endpoint;
}

function decodeJSONRPCSSE(value: string, requestId: string | number | undefined): unknown {
  const frames = value.replace(/\r\n/g, "\n").split(/\n\n+/);
  for (const frame of frames) {
    const parsed = parseSSEFrame(frame);
    if (!parsed || (parsed.event !== "" && parsed.event !== "message")) continue;
    const response = JSON.parse(parsed.data) as unknown;
    if (!isRecord(response) || response.id !== requestId) continue;
    return response;
  }
  throw new Error("Matching SSE response missing");
}

function boundedMCPTimeout(value: number | undefined): number {
  if (value === undefined) return DEFAULT_MCP_REQUEST_TIMEOUT_MS;
  const timeoutMs = Math.floor(value);
  if (!Number.isFinite(value) || timeoutMs < 1) {
    throw new AgentError("AGENT_MCP_CONFIG_INVALID", "MCP timeout is invalid", { phase: "mcp" });
  }
  return Math.min(timeoutMs, MAX_MCP_REQUEST_TIMEOUT_MS);
}

function mcpTransportError(message: string, _cause?: unknown): AgentError {
  return new AgentError("AGENT_MCP_TRANSPORT_ERROR", message, {
    retryable: true,
    phase: "mcp",
  });
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}
