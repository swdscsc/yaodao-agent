import {
  AgentError,
  AgentRuntimeClient,
  CustomHTTPToolExecutor,
  DeviceToolRouter,
  HostMCPHTTPTransport,
  MCPClient,
  MCPToolProvider,
  PlatformToolExecutor,
  ToolRegistry,
  asAgentError,
  log,
  normalizeMCPToolResult,
  type FunctionTool,
  type CancellationToken,
  type MCPToolDefinition,
  type AgentToolCall,
  type AgentToolArtifact,
  type AgentToolResult,
  type DeviceActionRequest,
  type MusicPlaylistItem,
  type ToolCatalogResponse,
  type ToolChoice,
  type ToolExecutionContext,
  type ToolExecutor,
  type ToolResolveClientTool,
} from "@listenai/agent-sdk";
import { normalizeToolSources } from "./toolPolicies";
import type { ServerDsaPolicy } from "./toolPolicies";
import { requestContext, type VoiceTurnContext } from "../types";

// URL syntax is validated here; the Host owns environment-specific egress policy.
const DEFER_HTTP_POLICY_TO_HOST = true;

export interface PreparedTools {
  registry: ToolRegistry;
  catalog: ToolCatalogResponse;
  toolChoice: ToolChoice;
  warnings: string[];
  close(): void;
}

export interface ToolProvider {
  prepare(context: VoiceTurnContext, policyContext?: ToolPreparationContext): Promise<PreparedTools>;
  resolveDeviceResult(sessionId: string, raw: unknown): boolean;
  cancelSession(sessionId: string, reason?: string): void;
  clearSession(sessionId: string): void;
}

export interface ToolPreparationContext {
  explicitDefinitions?: FunctionTool[];
  explicitBindings?: Record<string, unknown>;
  dsaPolicy?: ServerDsaPolicy;
}

export interface DefaultToolProviderOptions {
  localExecutors?: Record<string, ToolExecutor>;
  localTools?: Array<{ definition: FunctionTool; handlerId: string }>;
  httpTools?: HTTPToolDefinition[];
  disabledTools?: string[];
}

export interface HTTPToolDefinition {
  definition: FunctionTool;
  url: string;
  headers?: Record<string, string>;
  timeoutMs?: number;
  maxResponseBytes?: number;
  responseMapper?: (response: unknown, call: AgentToolCall) => unknown;
}

export interface MCPProviderEntry {
  serverId: string;
  provider: MCPToolProvider;
}

export interface MCPRegistrationResult {
  providers: MCPToolProvider[];
  warnings: string[];
}

export interface MCPConnection {
  index: number;
  serverId: string;
  provider: MCPToolProvider;
  tools: MCPToolDefinition[];
}

export interface MCPDiscoveryResult {
  connections: MCPConnection[];
  failures: Array<{ index: number; warning: string }>;
  warnings: string[];
}

export class DefaultToolProvider implements ToolProvider {
  private readonly deviceRouter = new DeviceToolRouter();
  private readonly localExecutors: Record<string, ToolExecutor>;
  private readonly localTools: Array<{ definition: FunctionTool; handlerId: string }>;
  private readonly disabledTools: Set<string>;

  constructor(options: DefaultToolProviderOptions = {}) {
    const httpTools = [...(options.httpTools ?? [])];
    const httpExecutors: Record<string, ToolExecutor> = {};
    const httpLocalTools = httpTools.map((tool) => {
      const handlerId = `http:${tool.definition.function.name}`;
      httpExecutors[handlerId] = new CustomHTTPToolExecutor({
        url: tool.url,
        headers: tool.headers,
        timeoutMs: tool.timeoutMs,
        maxResponseBytes: tool.maxResponseBytes,
        responseMapper: tool.responseMapper,
        allowInsecureHttp: DEFER_HTTP_POLICY_TO_HOST,
      });
      return { definition: tool.definition, handlerId };
    });
    this.localExecutors = { ...(options.localExecutors ?? {}), ...httpExecutors };
    this.localTools = [...(options.localTools ?? []), ...httpLocalTools];
    this.disabledTools = new Set(options.disabledTools ?? []);
  }

  async prepare(context: VoiceTurnContext, policyContext: ToolPreparationContext = {}): Promise<PreparedTools> {
    const startedAt = Date.now();
    safeLogInfo("official voice tools preparation started", {
      event: "tools.prepare.started",
      sessionId: context.sessionId,
      turnId: context.turnId,
      requestId: context.requestId,
    });
    const client = new AgentRuntimeClient({
      baseUrl: context.config.baseUrl,
      tokenSecretKey: context.config.platformTokenSecretKey,
    });
    const normalized = normalizeToolSources({
      tools: context.config.runtime.tools as unknown as FunctionTool[],
      toolBindings: context.config.runtime.toolBindings,
      mcpServers: context.config.runtime.mcpServers,
    });
    const clientBindings = new Map<string, unknown>();
    const mcpEntries: MCPProviderEntry[] = [];
    if (policyContext.dsaPolicy?.enabled !== true) {
      for (const [serverId, value] of Object.entries(normalized.mcpServers)) {
        if (serverId.startsWith("__system_mcp_")
          || !isRecord(value)
          || value.enabled === false
          || typeof value.url !== "string") continue;
        if (string(value.server_id).startsWith("__system_mcp_")) continue;
        const transport = new HostMCPHTTPTransport({
          sessionId: context.sessionId,
          transport: string(value.transport) === "sse" ? "sse" : "streamable_http",
          url: value.url,
          secretHeadersRef: typeof value.secretHeadersRef === "string" ? value.secretHeadersRef : undefined,
          allowInsecureHttp: DEFER_HTTP_POLICY_TO_HOST,
        });
        mcpEntries.push({
          serverId,
          provider: new MCPToolProvider(serverId, new MCPClient({ serverId, transport })),
        });
      }
    }
    if (mcpEntries.length > 0) {
      safeLogInfo("official voice MCP discovery started", {
        sessionId: context.sessionId,
        turnId: context.turnId,
        requestId: context.requestId,
        serverIds: mcpEntries.map((entry) => entry.serverId),
      });
    }
    const discovery = await connectMCPProviders(mcpEntries, context.cancellation);
    if (mcpEntries.length > 0) {
      safeLogInfo("official voice MCP discovery completed", {
        sessionId: context.sessionId,
        turnId: context.turnId,
        requestId: context.requestId,
        requestedServerCount: mcpEntries.length,
        connectedServerCount: discovery.connections.length,
        failedServerCount: discovery.failures.length,
        discoveredToolCount: discovery.connections.reduce((count, connection) => count + connection.tools.length, 0),
      });
    }
    const ownedProviders = new Set(discovery.connections.map(({ provider }) => provider));
    try {
      const discoveryFailures = new Map(
        discovery.failures.map((failure) => [failure.index, failure.warning]),
      );
      const mcpProviders = new Map<string, MCPToolProvider>();
      const mcpClientTools: ToolResolveClientTool[] = [];
      for (const connection of discovery.connections) {
        try {
          const preflight = new ToolRegistry();
          const aliases = connection.provider.registerConnectedTools(preflight, connection.tools);
          const definitions = preflight.definitions();
          for (const [index, definition] of definitions.entries()) {
            const originalName = aliases[definition.function.name];
            if (!originalName) throw new Error("MCP reverse alias missing");
            const bindingId = `mcp:${connection.serverId}:${index}`;
            clientBindings.set(bindingId, {
              type: "mcp",
              server_id: connection.serverId,
              original_name: originalName,
            });
            mcpClientTools.push({
              definition,
              binding_id: bindingId,
              priority: "configured",
              source: "external",
              enabled: true,
            });
          }
          mcpProviders.set(connection.serverId, connection.provider);
        } catch (error) {
          if (isCancellationError(error)) throw error;
          ownedProviders.delete(connection.provider);
          connection.provider.close();
          discoveryFailures.set(connection.index, `mcp:${connection.serverId}`);
        }
      }
      const clientTools = [
        ...buildClientToolCandidates(
          normalized,
          policyContext,
          context.config.runtime.legacyPolicy,
          clientBindings,
          this.localTools,
        ),
        ...mcpClientTools,
      ];
      const resolveStartedAt = Date.now();
      const resolved = await client.resolveTools(
        { client_tools: clientTools },
        requestContext(context, "tools-resolve"),
        context.cancellation,
      );
      const resolveDurationMs = Date.now() - resolveStartedAt;
      const catalog: ToolCatalogResponse = {
        tools: resolved.tools,
        tool_bindings: resolved.tool_bindings,
        device_capabilities: resolved.device_capabilities ?? [],
        etag: resolved.etag,
      };
      const registry = new ToolRegistry();
      const registryBuildStartedAt = Date.now();
      const discoveryWarnings = Array.from(discoveryFailures.entries())
        .sort(([left], [right]) => left - right)
        .map(([, warning]) => warning);
      const warnings: string[] = [...discoveryWarnings];
      const selectedProviders = new Set<MCPToolProvider>();
      const dispatchedDeviceActions = new Set<string>();
      const registeredToolNames = new Set<string>();
      const registrations: Array<{ definition: FunctionTool; executor: ToolExecutor }> = [];
      for (const definition of resolved.tools) {
        if (this.disabledTools.has(definition.function.name)) continue;
        const binding = resolved.tool_bindings[definition.function.name];
        const executor = this.executorFor(
          context,
          binding,
          definition.function.name,
          warnings,
          client,
          dispatchedDeviceActions,
          mcpProviders,
          clientBindings,
        );
        if (!executor) continue;
        registrations.push({ definition, executor });
        registeredToolNames.add(definition.function.name);
        const bindingRecord: Record<string, unknown> = isRecord(binding) ? binding : {};
        if (bindingRecord.type === "client") {
          const clientBinding = clientBindings.get(string(bindingRecord.binding_id));
          const clientBindingRecord: Record<string, unknown> = isRecord(clientBinding) ? clientBinding : {};
          if (clientBindingRecord.type === "mcp") {
            const provider = mcpProviders.get(string(clientBindingRecord.server_id));
            if (provider) selectedProviders.add(provider);
          }
        } else if (bindingRecord.type === "mcp") {
          const provider = mcpProviders.get(string(bindingRecord.server_id));
          if (provider) selectedProviders.add(provider);
        }
      }
      registry.registerBatch(registrations);
      const providers = Array.from(selectedProviders);
      for (const provider of ownedProviders) {
        if (selectedProviders.has(provider)) continue;
        ownedProviders.delete(provider);
        provider.close();
      }
      for (const warning of discoveryWarnings) {
        log.warn("MCP server unavailable", { serverId: warning.slice("mcp:".length) });
      }
      // Runtime may return a definition without a usable binding while an
      // environment is rolling out. Do not expose such a tool to the model:
      // it would be visible in the prompt but fail immediately with
      // AGENT_TOOL_NOT_FOUND when selected.
      const registryBuildDurationMs = Date.now() - registryBuildStartedAt;
      const catalogBuildStartedAt = Date.now();
      const unavailableToolNames = resolved.tools
        .map((definition) => definition.function.name)
        .filter((name) => !registeredToolNames.has(name));
      for (const name of unavailableToolNames) {
        warnings.push(`tool_executor_unavailable:${name}`);
      }
      const executableCatalog: ToolCatalogResponse = {
        ...catalog,
        tools: catalog.tools.filter((definition) => registeredToolNames.has(definition.function.name)),
        tool_bindings: Object.fromEntries(
          Object.entries(catalog.tool_bindings)
            .filter(([name]) => registeredToolNames.has(name)),
        ),
        device_capabilities: catalog.device_capabilities.filter((capability) => {
          const alias = typeof capability.alias === "string" ? capability.alias : "";
          return registeredToolNames.has(alias);
        }),
      };
      const catalogBuildDurationMs = Date.now() - catalogBuildStartedAt;
      const prepared: PreparedTools = {
        registry,
        catalog: executableCatalog,
        toolChoice: resolved.tool_choice ?? "auto",
        warnings,
        close(): void {
          closeMCPProviders(providers);
        },
      };
      safeLogInfo("official voice tools prepared", {
        sessionId: context.sessionId,
        turnId: context.turnId,
        requestId: context.requestId,
        durationMs: Date.now() - startedAt,
        resolveDurationMs,
        registryBuildDurationMs,
        catalogBuildDurationMs,
        resolveClientToolCount: clientTools.length,
        resolvedToolCount: resolved.tools.length,
        registeredToolCount: registeredToolNames.size,
        catalogToolCount: executableCatalog.tools.length,
        unavailableToolNames,
        mcpServerCount: mcpEntries.length,
        mcpConnectedCount: discovery.connections.length,
        warningCount: warnings.length,
        toolNames: Array.from(registeredToolNames),
        bindingTypes: Object.fromEntries(Array.from(registeredToolNames, (toolName) => {
          const binding = resolved.tool_bindings[toolName];
          return [toolName, isRecord(binding) ? string(binding.type) : "unknown"];
        })),
      });
      for (const provider of providers) ownedProviders.delete(provider);
      return prepared;
    } catch (error) {
      try {
        closeMCPProviders(ownedProviders);
      } catch {
        // Preserve the preparation failure after attempting every cleanup.
      }
      throw error;
    }
  }

  resolveDeviceResult(sessionId: string, raw: unknown): boolean {
    if (!isRecord(raw)
      || !hasOnlyKeys(raw, ["_type", "turn_id", "id", "result"])
      || typeof raw.turn_id !== "string"
      || typeof raw.id !== "string"
      || !isRecord(raw.result)) {
      return false;
    }
    const normalized = normalizeMCPToolResult(raw.result, raw.id);
    if (!normalized) return false;
    return this.deviceRouter.resolve({
      sessionId,
      turnId: raw.turn_id,
      callId: raw.id,
      result: {
        content: normalized.content,
        isError: normalized.isError,
        control: normalized.control,
        artifacts: normalized.artifacts,
      },
    });
  }

  cancelSession(sessionId: string, reason?: string): void {
    this.deviceRouter.cancelSession(sessionId, reason);
  }

  clearSession(sessionId: string): void {
    this.deviceRouter.cancelSession(sessionId, "Session state cleared");
  }

  private executorFor(
    context: VoiceTurnContext,
    value: unknown,
    toolName: string,
    warnings: string[],
    client: AgentRuntimeClient,
    dispatchedDeviceActions: Set<string>,
    mcpProviders: ReadonlyMap<string, MCPToolProvider>,
    clientBindings: ReadonlyMap<string, unknown>,
  ): ToolExecutor | null {
    if (!isRecord(value)) return null;
    const type = string(value.type) || string(value.kind);
    if (type === "platform") {
      const toolId = string(value.tool_id) || string(value.toolId);
      if (!toolId) return null;
      let executor: ToolExecutor = new PlatformToolExecutor({
        baseUrl: context.config.baseUrl,
        tokenSecretKey: context.config.platformTokenSecretKey,
        toolId,
        timeoutMs: number(value.timeout_ms) ?? number(value.timeoutMs),
        ...platformServerContext(value.server_context),
      });
      const policy = string(value.quota_failure_policy) || string(value.quotaFailurePolicy);
      if (policy === "return_tool_error") executor = new RecoverableQuotaExecutor(executor);
      return new PlatformArtifactDispatchExecutor(executor, client, dispatchedDeviceActions);
    }
    if (type === "device") {
      return this.deviceRouter.executor({
        protocol: string(value.protocol) === "xiaozhi" ? "xiaozhi" : "xiaoling",
        originalName: string(value.original_name) || string(value.originalName) || toolName,
        timeoutMs: number(value.timeout_ms) ?? number(value.timeoutMs),
      });
    }
    if (type === "http" || type === "custom_http") {
      const url = string(value.url);
      if (!url) return null;
      return new CustomHTTPToolExecutor({
        url,
        secretHeadersRef: string(value.secret_headers_ref) || string(value.secretHeadersRef) || undefined,
        timeoutMs: number(value.timeout_ms) ?? number(value.timeoutMs),
        maxResponseBytes: number(value.max_response_bytes) ?? number(value.maxResponseBytes),
        allowInsecureHttp: DEFER_HTTP_POLICY_TO_HOST,
      });
    }
    if (type === "local") {
      const handlerId = string(value.handler_id) || string(value.handlerId);
      const executor = this.localExecutors[handlerId];
      if (executor) return executor;
      warnings.push(`local:${toolName}:handler_missing`);
      return null;
    }
    if (type === "mcp") {
      const serverId = string(value.server_id);
      const originalName = string(value.original_name);
      const provider = mcpProviders.get(serverId);
      if (!provider || !originalName) {
        warnings.push(`mcp:${serverId || "unknown"}:binding_missing`);
        return null;
      }
      return provider.executorFor(originalName);
    }
    if (type === "client") {
      const bindingId = string(value.binding_id);
      const clientBinding = clientBindings.get(bindingId);
      if (!clientBinding || clientBinding === value) {
        warnings.push(`client:${bindingId || toolName}:binding_missing`);
        return null;
      }
      return this.executorFor(
        context,
        clientBinding,
        toolName,
        warnings,
        client,
        dispatchedDeviceActions,
        mcpProviders,
        clientBindings,
      );
    }
    return null;
  }
}

function buildClientToolCandidates(
  normalized: ReturnType<typeof normalizeToolSources>,
  policyContext: ToolPreparationContext,
  legacyPolicy: Record<string, unknown>,
  bindings: Map<string, unknown>,
  localTools: Array<{ definition: FunctionTool; handlerId: string }>,
): ToolResolveClientTool[] {
  const candidates: ToolResolveClientTool[] = [];
  const sources = configuredToolSources(legacyPolicy.toolSources);
  const append = (
    definitions: FunctionTool[] | undefined,
    sourceBindings: Record<string, unknown> | undefined,
    priority: "explicit" | "configured",
  ): void => {
    for (const [index, definition] of (definitions ?? []).entries()) {
      const name = definition.function.name;
      const source = priority === "configured" ? sources.get(name) : undefined;
      const binding = sourceBindings?.[name];
      let bindingId: string | undefined;
      if (binding !== undefined) {
        bindingId = `${priority}_${index}`;
        bindings.set(bindingId, binding);
      }
      candidates.push({
        definition,
        ...(bindingId ? { binding_id: bindingId } : {}),
        priority,
        ...(source?.source ? { source: source.source } : {}),
        enabled: source?.enabled !== false,
      });
    }
  };
  append(policyContext.explicitDefinitions, policyContext.explicitBindings, "explicit");
  for (const [index, item] of localTools.entries()) {
    const bindingId = `local_${index}`;
    bindings.set(bindingId, { type: "local", handler_id: item.handlerId });
    candidates.push({
      definition: item.definition,
      binding_id: bindingId,
      priority: "explicit",
      enabled: true,
    });
  }
  append(normalized.definitions, normalized.bindings, "configured");
  return candidates;
}

function configuredToolSources(value: unknown): Map<string, { source?: ToolResolveClientTool["source"]; enabled: boolean }> {
  const output = new Map<string, { source?: ToolResolveClientTool["source"]; enabled: boolean }>();
  if (!Array.isArray(value)) return output;
  for (const raw of value) {
    if (!isRecord(raw)) continue;
    const name = string(raw.name);
    if (!name) continue;
    const rawSource = string(raw.source);
    const source = rawSource === "external" || rawSource === "xiaoling" ? rawSource : undefined;
    output.set(name, {
      ...(source ? { source } : {}),
      enabled: raw.enabled !== false,
    });
  }
  return output;
}

/** Connects independently, then registers deterministically so model tool order is stable. */
export async function connectAndRegisterMCPProviders(
  entries: MCPProviderEntry[],
  registry: ToolRegistry,
  cancellation: CancellationToken,
  maxConcurrency = 4,
): Promise<MCPRegistrationResult> {
  const discovery = await connectMCPProviders(entries, cancellation, maxConcurrency);
  const warnings = new Map(discovery.failures.map((failure) => [failure.index, failure.warning]));
  const connected: MCPToolProvider[] = [];
  for (const connection of discovery.connections) {
    try {
      cancellation.throwIfCancelled();
      connection.provider.registerConnectedTools(registry, connection.tools);
      connected.push(connection.provider);
    } catch (error) {
      if (isCancellationError(error)) {
        closeMCPEntries(entries);
        throw error;
      }
      connection.provider.close();
      warnings.set(connection.index, `mcp:${connection.serverId}`);
    }
  }
  return {
    providers: connected,
    warnings: Array.from(warnings.entries())
      .sort(([left], [right]) => left - right)
      .map(([, warning]) => warning),
  };
}

export async function connectMCPProviders(
  entries: MCPProviderEntry[],
  cancellation: CancellationToken,
  maxConcurrency = 4,
): Promise<MCPDiscoveryResult> {
  if (entries.length === 0) return { connections: [], failures: [], warnings: [] };
  const concurrency = Math.max(1, Math.min(Math.floor(maxConcurrency) || 1, 8, entries.length));
  const discovered = new Array<MCPToolDefinition[] | undefined>(entries.length);
  const warnings = new Array<string | undefined>(entries.length);
  let nextIndex = 0;
  let cancellationFailure: unknown;

  const worker = async (): Promise<void> => {
    while (cancellationFailure === undefined) {
      const index = nextIndex;
      nextIndex += 1;
      if (index >= entries.length) return;
      const entry = entries[index];
      try {
        cancellation.throwIfCancelled();
        discovered[index] = await entry.provider.connect(cancellation);
      } catch (error) {
        entry.provider.close();
        if (isCancellationError(error)) {
          cancellationFailure = error;
          return;
        }
        warnings[index] = `mcp:${entry.serverId}`;
      }
    }
  };

  await Promise.all(Array.from({ length: concurrency }, () => worker()));
  try {
    if (cancellationFailure !== undefined) throw cancellationFailure;
    cancellation.throwIfCancelled();
  } catch (error) {
    closeMCPEntries(entries);
    throw error;
  }

  const connections: MCPConnection[] = [];
  for (let index = 0; index < entries.length; index += 1) {
    const tools = discovered[index];
    if (!tools) continue;
    const entry = entries[index];
    connections.push({ index, serverId: entry.serverId, provider: entry.provider, tools });
  }
  const failures = warnings.flatMap((warning, index) => warning ? [{ index, warning }] : []);
  return {
    connections,
    failures,
    warnings: failures.map(({ warning }) => warning),
  };
}

function closeMCPEntries(entries: MCPProviderEntry[]): void {
  closeMCPProviders(entries.map(({ provider }) => provider));
}

function closeMCPProviders(providers: Iterable<MCPToolProvider>): void {
  let firstError: unknown;
  for (const provider of providers) {
    try {
      provider.close();
    } catch (error) {
      if (firstError === undefined) firstError = error;
    }
  }
  if (firstError !== undefined) throw firstError;
}

function isCancellationError(error: unknown): boolean {
  return error instanceof AgentError && error.code === "AGENT_CANCELLED";
}

class RecoverableQuotaExecutor implements ToolExecutor {
  constructor(private readonly delegate: ToolExecutor) {}

  async execute(call: AgentToolCall, context: ToolExecutionContext): Promise<AgentToolResult> {
    try {
      return await this.delegate.execute(call, context);
    } catch (error) {
      const normalized = asAgentError(error, "AGENT_TOOL_EXECUTION_FAILED", "tool");
      if (normalized.code !== "AGENT_CAPABILITY_QUOTA_EXCEEDED") throw normalized;
      return {
        callId: call.id,
        content: [{ type: "text", text: normalized.message }],
        isError: true,
        control: { agentStop: false },
        artifacts: [],
      };
    }
  }

  cancel(callId: string, reason?: string): void {
    this.delegate.cancel?.(callId, reason);
  }
}

class PlatformArtifactDispatchExecutor implements ToolExecutor {
  constructor(
    private readonly delegate: ToolExecutor,
    private readonly client: AgentRuntimeClient,
    private readonly dispatched: Set<string>,
  ) {}

  async execute(call: AgentToolCall, context: ToolExecutionContext): Promise<AgentToolResult> {
    const result = await this.delegate.execute(call, context);
    let sequence = 0;
    for (const artifact of result.artifacts) {
      const action = deviceActionFromArtifact(artifact);
      if (!action) continue;
      const identity = JSON.stringify(action);
      if (this.dispatched.has(identity)) continue;
      context.cancellation.throwIfCancelled();
      this.dispatched.add(identity);
      sequence += 1;
      await this.client.dispatchDeviceAction(action, {
        sessionId: context.sessionId,
        turnId: context.turnId,
        requestId: boundedCorrelation(`${context.requestId}:device-action:${sequence}`),
        appId: context.appId,
        toolCallId: call.id,
      }, context.cancellation);
    }
    return result;
  }

  cancel(callId: string, reason?: string, owner?: { sessionId: string; turnId: string }): void {
    this.delegate.cancel?.(callId, reason, owner);
  }
}

const MUSIC_PLAYBACK = new Set(["kuwo", "netease", "general", "audio_link", "tf_card"]);

function deviceActionFromArtifact(artifact: AgentToolArtifact): DeviceActionRequest | null {
  if (artifact.type === "music_playlist"
    && MUSIC_PLAYBACK.has(String(artifact.playback))
    && Array.isArray(artifact.items)) {
    return {
      action: "music_playlist",
      playback: artifact.playback as "kuwo" | "netease" | "general" | "audio_link" | "tf_card",
      items: artifact.items as MusicPlaylistItem[],
    };
  }
  if (artifact.type === "device_action"
    && (artifact.action === "netease_token_refresh" || artifact.action === "playback_exit")) {
    return { action: artifact.action };
  }
  return null;
}

function boundedCorrelation(value: string): string {
  return value.length <= 128 ? value : value.slice(value.length - 128);
}

function safeLogInfo(message: string, fields: Record<string, unknown>): void {
  try {
    log.info(message, fields);
  } catch {
    // Logging must not change tool preparation behavior in lightweight hosts.
  }
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function string(value: unknown): string {
  return typeof value === "string" ? value : "";
}

function number(value: unknown): number | undefined {
  return typeof value === "number" && Number.isFinite(value) ? value : undefined;
}

function platformServerContext(value: unknown): {
  serverContext?: { type: "netease_music"; secretRef: string };
} {
  if (!isRecord(value) || value.type !== "netease_music") return {};
  const secretRef = string(value.secret_ref);
  return secretRef
    ? { serverContext: { type: "netease_music", secretRef } }
    : {};
}

function hasOnlyKeys(value: Record<string, unknown>, allowed: string[]): boolean {
  const names = new Set(allowed);
  return Object.keys(value).every((key) => names.has(key));
}
