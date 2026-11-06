import type { HTTPStreamHandlers, HTTPStreamRequest } from "../host";
import { decodeUTF8, encodeUTF8 } from "./utf8";
import { AgentCancelledError, type CancellationToken } from "../runtime/cancellation";
import { AgentError } from "../runtime/errors";

export type HTTPJSONHeaders = Record<string, string> | Array<[string, string]>;

export interface HTTPJSONRequest {
  method: string;
  url: string;
  headers?: HTTPJSONHeaders;
  body?: unknown;
  timeoutMs?: number;
  maxResponseBytes?: number;
}

/** Event-driven JSON HTTP used by developer-owned Agent services. */
export class HTTPJSONClient {
  async request<T = unknown>(request: HTTPJSONRequest, cancellation: CancellationToken): Promise<T> {
    cancellation.throwIfCancelled();
    const headers = normalizeHeaders(request.headers, request.body !== undefined);
    const body = request.body === undefined || request.body === null
      ? null
      : request.body instanceof Uint8Array
        ? request.body
        : encodeUTF8(JSON.stringify(request.body));
    const maxResponseBytes = boundedResponseBytes(request.maxResponseBytes);
    const transportRequest: HTTPStreamRequest = {
      method: request.method,
      url: request.url,
      headers,
      body,
      responseMode: "buffer",
      ...(request.timeoutMs ? { totalTimeoutMs: boundedTimeout(request.timeoutMs) } : {}),
      maxResponseBytes,
    };

    return new Promise<T>((resolve, reject) => {
      let streamId = "";
      let settled = false;
      let status = 0;
      let contentType = "";
      let totalBytes = 0;
      const chunks: Uint8Array[] = [];
      let unsubscribe: () => void = () => undefined;
      const finishError = (error: AgentError, cancel = false): void => {
        if (settled) return;
        settled = true;
        unsubscribe();
        if (cancel && streamId) {
          try {
            host.httpStreamCancel(streamId);
          } catch {
            // Preserve the original request error.
          }
        }
        reject(error);
      };
      const handlers: HTTPStreamHandlers = {
        onHeaders(value, responseHeaders): void {
          status = value;
          for (const [name, headerValue] of responseHeaders) {
            if (name.toLowerCase() === "content-type") contentType = headerValue;
          }
        },
        onChunk(chunk): void {
          totalBytes += chunk.length;
          if (totalBytes > maxResponseBytes) {
            finishError(new AgentError("AGENT_HTTP_RESPONSE_TOO_LARGE", "HTTP response is too large", {
              retryable: false,
              phase: "transport",
            }), true);
            return;
          }
          chunks.push(chunk);
        },
        onDone(): void {
          if (settled) return;
          if (status < 200 || status >= 300) {
            finishError(new AgentError("AGENT_HTTP_REQUEST_FAILED", "HTTP request failed", {
              retryable: status >= 500,
              phase: "transport",
            }));
            return;
          }
          if (contentType && !isJSONMediaType(contentType)) {
            finishError(new AgentError("AGENT_HTTP_RESPONSE_INVALID", "HTTP response is not JSON", {
              phase: "transport",
            }));
            return;
          }
          try {
            const bytes = joinChunks(chunks, totalBytes);
            const value = JSON.parse(decodeUTF8(bytes)) as T;
            settled = true;
            unsubscribe();
            resolve(value);
          } catch {
            finishError(new AgentError("AGENT_HTTP_RESPONSE_INVALID", "HTTP response JSON is invalid", {
              phase: "transport",
            }));
          }
        },
        onError(error): void {
          finishError(new AgentError("AGENT_HTTP_REQUEST_FAILED", "HTTP request failed", {
            retryable: error.retryable,
            phase: "transport",
          }));
        },
      };
      try {
        streamId = host.httpStreamStart(transportRequest, handlers);
        unsubscribe = cancellation.onCancel((reason) => finishError(
          new AgentCancelledError(reason || "HTTP request cancelled"),
          true,
        ));
        if (settled) unsubscribe();
      } catch {
        finishError(new AgentError("AGENT_HTTP_REQUEST_FAILED", "HTTP request could not be opened", {
          retryable: true,
          phase: "transport",
        }));
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

function normalizeHeaders(headers: HTTPJSONHeaders | undefined, hasBody: boolean): Array<[string, string]> {
  const entries = Array.isArray(headers) ? headers : Object.entries(headers ?? {});
  const output = entries.map(([name, value]) => [name, value] as [string, string]);
  if (!output.some(([name]) => name.toLowerCase() === "accept")) output.push(["Accept", "application/json"]);
  if (hasBody && !output.some(([name]) => name.toLowerCase() === "content-type")) {
    output.push(["Content-Type", "application/json"]);
  }
  return output;
}

function isJSONMediaType(value: string): boolean {
  const mediaType = value.split(";", 1)[0].trim().toLowerCase();
  return mediaType === "application/json"
    || (mediaType.startsWith("application/") && mediaType.endsWith("+json"));
}

function boundedResponseBytes(value?: number): number {
  if (!Number.isFinite(value) || Number(value) <= 0) return 1 << 20;
  return Math.min(Math.floor(Number(value)), 8 << 20);
}

function boundedTimeout(value: number): number {
  return Math.min(Math.max(Math.floor(value), 1), 120_000);
}
