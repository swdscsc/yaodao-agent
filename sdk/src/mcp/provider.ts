import type { FunctionTool } from "../model/types";
import type { CancellationToken } from "../runtime/cancellation";
import { AgentError } from "../runtime/errors";
import { ToolRegistry } from "../tools/registry";
import type { ToolExecutor, ToolResult } from "../tools/types";
import type { MCPToolDefinition } from "./client";

export interface MCPClientLike {
  connect(cancellation: CancellationToken): Promise<MCPToolDefinition[]>;
  callTool(
    name: string,
    args: Record<string, unknown>,
    callId: string,
    cancellation: CancellationToken,
  ): Promise<ToolResult>;
  close(): void;
}

export interface McpServerConfig {
  enabled: boolean;
  transport: "streamable_http" | "sse";
  url: string;
  secretHeadersRef?: string;
}

export class MCPToolProvider {
  constructor(
    private readonly serverId: string,
    private readonly client: MCPClientLike,
  ) {}

  async registerTools(
    registry: ToolRegistry,
    cancellation: CancellationToken,
  ): Promise<Record<string, string>> {
    try {
      const tools = await this.connect(cancellation);
      return this.registerConnectedTools(registry, tools);
    } catch (error) {
      this.client.close();
      throw error;
    }
  }

  connect(cancellation: CancellationToken): Promise<MCPToolDefinition[]> {
    return this.client.connect(cancellation);
  }

  registerConnectedTools(
    registry: ToolRegistry,
    tools: MCPToolDefinition[],
  ): Record<string, string> {
    const used = new Set(registry.definitions().map((definition) => definition.function.name));
    const aliases: Record<string, string> = {};
    const registrations: Array<{ definition: FunctionTool; originalName: string }> = [];
    for (const tool of tools) {
      const alias = safeMCPToolAlias(this.serverId, tool.name, used);
      used.add(alias);
      aliases[alias] = tool.name;
      const definition: FunctionTool = {
        type: "function",
        function: {
          name: alias,
          description: tool.description,
          parameters: tool.inputSchema,
        },
      };
      registrations.push({ definition, originalName: tool.name });
    }
    registry.registerBatch(registrations.map((registration) => ({
      definition: registration.definition,
      executor: this.executorFor(registration.originalName),
    })));
    return aliases;
  }

  executorFor(originalName: string): ToolExecutor {
    return {
      execute: (call, context) => this.client.callTool(
        originalName,
        call.parsedArguments,
        call.id,
        context.cancellation,
      ),
    };
  }

  close(): void {
    this.client.close();
  }
}

export function safeMCPToolAlias(serverId: string, toolName: string, used: Set<string>): string {
  const base = safeName(toolName) || "tool";
  if (base.length <= 64 && !used.has(base)) return base;
  const prefix = safeName(serverId) || "mcp";
  const hash = shortHash(`${serverId}\u0000${toolName}`);
  const suffix = `_${hash}`;
  const available = 64 - prefix.length - suffix.length - 1;
  if (available < 1) {
    throw new AgentError("AGENT_MCP_TOOL_ALIAS_INVALID", "Unable to create MCP tool alias", {
      phase: "mcp",
    });
  }
  return `${prefix}_${base.slice(0, available)}${suffix}`;
}

function safeName(value: string): string {
  return value.replace(/[^A-Za-z0-9_-]/g, "_").replace(/_+/g, "_").replace(/^_+|_+$/g, "");
}

function shortHash(value: string): string {
  let hash = 2166136261;
  for (let index = 0; index < value.length; index += 1) {
    hash ^= value.charCodeAt(index);
    hash = Math.imul(hash, 16777619);
  }
  return (hash >>> 0).toString(36).slice(0, 7);
}
