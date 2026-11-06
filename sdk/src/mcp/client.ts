import type { CancellationToken } from "../runtime/cancellation";
import { AgentError } from "../runtime/errors";
import type { ToolContent, ToolResult } from "../tools/types";
import { normalizeClosedToolResult } from "../tools/types";

export interface JSONRPCRequest {
  jsonrpc: "2.0";
  id?: string;
  method: string;
  params?: Record<string, unknown>;
}

export interface MCPTransport {
  request(request: JSONRPCRequest, cancellation: CancellationToken): Promise<unknown>;
  close(): void;
}

export interface MCPToolDefinition {
  name: string;
  description?: string;
  inputSchema: Record<string, unknown>;
}

export interface MCPClientOptions {
  serverId: string;
  transport: MCPTransport;
  supportedProtocolVersions?: string[];
  maxTools?: number;
  maxPages?: number;
}

export class MCPClient {
  private readonly serverId: string;
  private readonly transport: MCPTransport;
  private readonly supportedProtocolVersions: string[];
  private readonly maxTools: number;
  private readonly maxPages: number;
  private nextId = 0;
  private connected = false;
  private closed = false;

  constructor(options: MCPClientOptions) {
    this.serverId = options.serverId;
    this.transport = options.transport;
    this.supportedProtocolVersions = options.supportedProtocolVersions ?? ["2025-03-26", "2024-11-05"];
    this.maxTools = options.maxTools ?? 128;
    this.maxPages = options.maxPages ?? 16;
  }

  async connect(cancellation: CancellationToken): Promise<MCPToolDefinition[]> {
    if (this.closed) throw mcpError("MCP client is closed");
    if (this.connected) throw mcpError("MCP client is already connected");
    cancellation.throwIfCancelled();
    try {
      const initialized = await this.call("initialize", {
        protocolVersion: this.supportedProtocolVersions[0],
        capabilities: {},
        clientInfo: { name: "listenai-agent-sdk", version: "1.0.0" },
      }, cancellation);
      if (!isRecord(initialized) || typeof initialized.protocolVersion !== "string") {
        throw mcpError("Invalid MCP initialize result");
      }
      if (!this.supportedProtocolVersions.includes(initialized.protocolVersion)) {
        throw mcpError("Unsupported MCP protocol version");
      }
      await this.notify("notifications/initialized", {}, cancellation);
      const tools = await this.listTools(cancellation);
      this.connected = true;
      return tools;
    } catch (error) {
      this.transport.close();
      throw error;
    }
  }

  async callTool(
    name: string,
    args: Record<string, unknown>,
    callId: string,
    cancellation: CancellationToken,
  ): Promise<ToolResult> {
    if (!this.connected || this.closed) throw mcpError("MCP client is not connected");
    try {
      const result = await this.call("tools/call", { name, arguments: args }, cancellation, "AGENT_MCP_TOOL_ERROR");
      if (!isRecord(result) || !Array.isArray(result.content)) {
        throw mcpError("Invalid MCP tool result");
      }
      const normalized = normalizeMCPToolResult(result, callId);
      if (!normalized) throw mcpError("Invalid MCP tool result");
      return normalized;
    } catch (error) {
      if (isFatalToolCallError(error)) this.close();
      throw error;
    }
  }

  close(): void {
    if (this.closed) return;
    this.closed = true;
    this.connected = false;
    this.transport.close();
  }

  private async listTools(cancellation: CancellationToken): Promise<MCPToolDefinition[]> {
    const tools: MCPToolDefinition[] = [];
    let cursor: string | undefined;
    for (let page = 0; page < this.maxPages; page += 1) {
      const params = cursor ? { cursor } : {};
      const result = await this.call("tools/list", params, cancellation);
      if (!isRecord(result) || !Array.isArray(result.tools)) throw mcpError("Invalid MCP tools/list result");
      for (const raw of result.tools) {
        tools.push(normalizeToolDefinition(raw));
        if (tools.length > this.maxTools) throw mcpError("MCP tool limit exceeded");
      }
      cursor = typeof result.nextCursor === "string" && result.nextCursor ? result.nextCursor : undefined;
      if (!cursor) return tools;
    }
    throw mcpError("MCP pagination limit exceeded");
  }

  private async call(
    method: string,
    params: Record<string, unknown>,
    cancellation: CancellationToken,
    errorCode = "AGENT_MCP_PROTOCOL_ERROR",
  ): Promise<unknown> {
    cancellation.throwIfCancelled();
    const id = `${this.serverId}:${++this.nextId}`;
    const response = await this.transport.request({ jsonrpc: "2.0", id, method, params }, cancellation);
    if (!isRecord(response) || response.jsonrpc !== "2.0" || response.id !== id) {
      throw mcpError("Invalid JSON-RPC response");
    }
    if (isRecord(response.error)) {
      const message = errorCode === "AGENT_MCP_TOOL_ERROR"
        ? "MCP tool request failed"
        : "MCP request failed";
      throw mcpError(message, errorCode);
    }
    if (!("result" in response)) throw mcpError("JSON-RPC result is missing");
    return response.result;
  }

  private async notify(
    method: string,
    params: Record<string, unknown>,
    cancellation: CancellationToken,
  ): Promise<void> {
    cancellation.throwIfCancelled();
    await this.transport.request({ jsonrpc: "2.0", method, params }, cancellation);
  }
}

function isFatalToolCallError(error: unknown): boolean {
  return !(error instanceof AgentError)
    || (error.code !== "AGENT_MCP_TOOL_ERROR" && error.code !== "AGENT_CANCELLED");
}

function normalizeToolDefinition(value: unknown): MCPToolDefinition {
  if (!isRecord(value) || typeof value.name !== "string" || !value.name || !isRecord(value.inputSchema)) {
    throw mcpError("Invalid MCP tool definition");
  }
  return {
    name: value.name,
    description: typeof value.description === "string" ? value.description : undefined,
    inputSchema: value.inputSchema,
  };
}

export function normalizeMCPToolResult(value: unknown, callId: string): ToolResult | null {
  if (!isRecord(value)
    || !hasOnlyKeys(value, ["content", "isError", "control", "artifacts", "structuredContent", "_meta"])
    || !Array.isArray(value.content)
    || (value.isError !== undefined && typeof value.isError !== "boolean")
    || (value.artifacts !== undefined && !Array.isArray(value.artifacts))) return null;
  let control = { agentStop: false };
  if (value.control !== undefined) {
    if (!isRecord(value.control)
      || !hasOnlyKeys(value.control, ["agentStop"])
      || typeof value.control.agentStop !== "boolean") return null;
    control = { agentStop: value.control.agentStop };
  }
  const content = normalizeMCPContent(value.content);
  if (!content) return null;
  return normalizeClosedToolResult({
    content,
    isError: value.isError === true,
    control,
    artifacts: value.artifacts ?? [],
  }, callId);
}

function normalizeMCPContent(values: unknown[]): ToolContent[] | null {
  const content: ToolContent[] = [];
  for (const value of values) {
    const normalized = normalizeMCPContentItem(value);
    if (!normalized) return null;
    content.push(normalized);
  }
  return content;
}

function normalizeMCPContentItem(value: unknown): ToolContent | null {
  if (!isRecord(value) || typeof value.type !== "string") return null;
  if (value.type === "text") {
    return hasOnlyKeys(value, ["type", "text", "annotations", "_meta"])
      && typeof value.text === "string"
      ? { type: "text", text: value.text }
      : null;
  }
  if (value.type === "image" || value.type === "audio") {
    if (!hasOnlyKeys(value, ["type", "data", "mimeType", "annotations", "_meta"])
      || typeof value.data !== "string"
      || typeof value.mimeType !== "string") return null;
    const canonical = value.type === "image"
      ? {
        type: "image" as const,
        kind: "unknown" as const,
        data: `data:${value.mimeType};base64,${value.data}`,
        mime_type: value.mimeType,
      }
      : {
        type: "audio" as const,
        data: `data:${value.mimeType};base64,${value.data}`,
        mime_type: value.mimeType,
      };
    return normalizeClosedToolResult({
      content: [canonical],
      isError: false,
      control: { agentStop: false },
      artifacts: [],
    }, "mcp-content")?.content[0] ?? null;
  }
  if (value.type !== "resource"
    || !hasOnlyKeys(value, ["type", "resource", "annotations", "_meta"])
    || !isRecord(value.resource)
    || !hasOnlyKeys(value.resource, ["uri", "mimeType", "text", "blob", "_meta"])
    || typeof value.resource.uri !== "string"
    || (value.resource.mimeType !== undefined && typeof value.resource.mimeType !== "string")
    || (value.resource.text !== undefined && typeof value.resource.text !== "string")
    || (value.resource.blob !== undefined && typeof value.resource.blob !== "string")
    || (value.resource.text !== undefined && value.resource.blob !== undefined)) return null;
  const mimeType = typeof value.resource.mimeType === "string"
    ? value.resource.mimeType
    : value.resource.blob !== undefined
      ? "application/octet-stream"
      : undefined;
  const canonical: Record<string, unknown> = {
    type: "resource",
    ...(value.resource.uri.startsWith("https://") ? { uri: value.resource.uri } : {}),
    ...(value.resource.text !== undefined ? { text: value.resource.text } : {}),
    ...(value.resource.blob !== undefined && mimeType
      ? { data: `data:${mimeType};base64,${value.resource.blob}` }
      : {}),
    ...(mimeType ? { mime_type: mimeType } : {}),
  };
  return normalizeClosedToolResult({
    content: [canonical],
    isError: false,
    control: { agentStop: false },
    artifacts: [],
  }, "mcp-content")?.content[0] ?? null;
}

function mcpError(message: string, code = "AGENT_MCP_PROTOCOL_ERROR"): AgentError {
  return new AgentError(code, message, { phase: "mcp" });
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function hasOnlyKeys(value: Record<string, unknown>, allowed: string[]): boolean {
  const names = new Set(allowed);
  return Object.keys(value).every((key) => names.has(key));
}
