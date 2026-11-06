import { validateFunctionToolDefinition, type FunctionTool } from "@listenai/agent-sdk";
import { adaptLegacyConfig, OFFICIAL_DEFAULT_MODEL } from "./legacyConfigAdapter";

export type JsonPrimitive = string | number | boolean | null;
export type JsonValue = JsonPrimitive | JsonRecord | JsonValue[];
export interface JsonRecord { [key: string]: JsonValue | undefined; }

export interface PlatformModelConfig {
  type: "platform";
  model: string;
}

export interface OpenAICompatibleModelConfig {
  type: "openai_compatible";
  baseUrl: string;
  apiKeySecretKey: string;
  model: string;
  headersSecretKey?: string;
  extraBody?: JsonRecord;
}

export type NormalizedModelProvider = PlatformModelConfig | OpenAICompatibleModelConfig;

export interface NormalizedAgentRuntimeConfig {
  schemaVersion: "1.0";
  model: {
    primary: NormalizedModelProvider;
    fallback?: NormalizedModelProvider;
    temperature?: number;
    maxTokens?: number;
    timeoutMs?: number;
    maxRetries?: number;
    sidecars?: Record<string, NormalizedModelProvider>;
  };
  react: {
    maxSteps: number;
    maxToolCalls: number;
    duplicateToolCalls: "reject";
    toolExecution: "serial";
  };
  capabilities: Record<string, boolean>;
  tools: JsonValue[];
  toolBindings: JsonRecord;
  mcpServers: JsonRecord;
  legacyPolicy: JsonRecord;
}

export interface NormalizedSessionConfig {
  baseUrl: string;
  platformTokenSecretKey: string;
  agentJsVersion?: string;
  agentBundleAppId?: string;
  businessAppId?: string;
  xiaolingVersion?: string;
  // Legacy compatibility for templates that still read the business App from llmApp.
  llmApp?: string;
  // Request-scoped feature markers from the NLP config frame. These are kept
  // separate from agent_runtime capabilities so debug-only switches cannot
  // silently change the normal tool policy.
  features?: string[];
  nlu: JsonRecord;
  tts: JsonRecord;
  runtime: NormalizedAgentRuntimeConfig;
}

export interface NormalizedConfigFrame {
  publicConfig: NormalizedSessionConfig;
  secrets: Record<string, string>;
  warnings: string[];
}

export function normalizeConfigFrame(value: unknown, secretNamespace = ""): NormalizedConfigFrame {
  if (!isRecord(value)) throw new Error("Config frame must be an object");
  const frameNlu = recordValue(value.nluProperty);
  const requestInput = mergeRecords(recordValue(frameNlu.input), recordValue(value.input));
  const nlu = mergeRecords(frameNlu, requestInput, { input: requestInput });
  const canonical = recordValue(nlu.agent_runtime);
  requireOnlyKeys(canonical, [
    "schema_version",
    "model",
    "react",
    "capabilities",
    "tools",
    "tool_bindings",
    "mcp_servers",
  ], "agent_runtime");
  const schemaVersion = stringValue(canonical.schema_version) || "1.0";
  if (schemaVersion !== "1.0") throw new Error("Unsupported agent_runtime schema_version");
  const secrets: Record<string, string> = {};
  const secretWarnings: string[] = [];
  const validationWarnings: string[] = [];
  const token = stringValue(value.token);
  const platformTokenSecretKey = secretName(secretNamespace, "platform.token");
  if (token) secrets[platformTokenSecretKey] = token;
  extractLegacySecrets(nlu, secrets, secretNamespace, secretWarnings);
  const legacy = adaptLegacyConfig(nlu);
  requireOptionalRecord(canonical.model, "agent_runtime.model");
  requireOptionalRecord(canonical.react, "agent_runtime.react");
  requireOptionalRecord(canonical.capabilities, "agent_runtime.capabilities");
  requireOptionalRecord(canonical.tool_bindings, "agent_runtime.tool_bindings");
  requireOptionalRecord(canonical.mcp_servers, "agent_runtime.mcp_servers");
  const canonicalModel = recordValue(canonical.model);
  requireOnlyKeys(canonicalModel, [
    "primary",
    "fallback",
    "temperature",
    "max_tokens",
    "timeout_ms",
    "max_retries",
    "sidecars",
  ], "agent_runtime.model");
  requireOptionalRecord(canonicalModel.sidecars, "agent_runtime.model.sidecars");
  const legacyModel = legacy.runtime.model;
  const primary = normalizeModelProvider(
    canonicalModel.primary,
    "model.primary",
    secrets,
    secretNamespace,
  ) ?? legacyModel?.primary ?? { type: "platform", model: OFFICIAL_DEFAULT_MODEL };
  const fallback = normalizeModelProvider(canonicalModel.fallback, "model.fallback", secrets, secretNamespace)
    ?? legacyModel?.fallback;
  const sidecars = normalizeSidecars(recordValue(canonicalModel.sidecars), secrets, secretNamespace);
  if (Object.keys(sidecars).length === 0 && legacyModel?.sidecars) {
    Object.assign(sidecars, legacyModel.sidecars);
  }
  const canonicalCapabilities = booleanRecord(canonical.capabilities, true);
  const canonicalTools = Array.isArray(canonical.tools) ? normalizeToolDefinitions(canonical.tools, true) : undefined;
  if (canonical.tools !== undefined && !Array.isArray(canonical.tools)) {
    throw new Error("agent_runtime.tools must be an array");
  }
  const tools = canonicalTools ?? normalizeToolDefinitions(legacy.runtime.tools ?? [], false);
  const toolBindings = {
    ...normalizeLegacyToolBindings(nlu.agent_tools, secrets, secretNamespace),
    ...normalizeToolBindings(recordValue(canonical.tool_bindings), secrets, secretNamespace, true),
  };
  validateBindingReferences(toolBindings, tools);
  const rawMCP = isRecord(canonical.mcp_servers)
    ? canonical.mcp_servers
    : recordValue(legacy.runtime.mcpServers);
  const mcpServers = normalizeMCPServers(
    rawMCP,
    secrets,
    secretNamespace,
    validationWarnings,
  );
  const neteaseMusicSecretRef = secretName(secretNamespace, "integration.netease_music");
  const runtime: NormalizedAgentRuntimeConfig = {
    schemaVersion: "1.0",
    model: {
      primary,
      ...(fallback ? { fallback } : {}),
      ...optionalBoundedNumber("temperature", canonicalModel.temperature, 0, 2, false),
      ...optionalBoundedNumber("maxTokens", canonicalModel.max_tokens, 1, 65_536, true),
      ...optionalBoundedNumber("timeoutMs", canonicalModel.timeout_ms, 1, 120_000, true),
      ...optionalBoundedNumber("maxRetries", canonicalModel.max_retries, 0, 5, true),
      ...(Object.keys(sidecars).length > 0 ? { sidecars } : {}),
    },
    react: normalizeReact(recordValue(canonical.react)),
    capabilities: {
      ...(legacy.runtime.capabilities ?? {}),
      ...canonicalCapabilities,
    },
    tools,
    toolBindings,
    mcpServers,
    legacyPolicy: {
      ...clone(legacy.runtime.legacyPolicy ?? {}),
      ...(secrets[neteaseMusicSecretRef] && stringValue(nlu.music_source) === "netease_official"
        ? {
          neteaseMusic: {
            enabled: true,
            secretRef: neteaseMusicSecretRef,
          },
        }
        : {}),
      ...(Array.isArray(canonical.tools)
        ? { toolSources: summarizeToolSources(canonical.tools) }
        : {}),
    },
  };
  const publicNlu = redactNlu(nlu);
  const features = normalizeFeatures(value.features);
  const businessAppId = stringValue(value.businessAppId) || stringValue(value.llmApp);
  const agentJsVersion = stringValue(value.agentJsVersion);
  const agentBundleAppId = stringValue(value.agentBundleAppId);
  const xiaolingVersion = stringValue(value.xiaolingVersion);
  if (agentJsVersion) validateIdentifier(agentJsVersion, "Agent JS version", 128);
  if (agentBundleAppId) validateIdentifier(agentBundleAppId, "Agent bundle App ID", 128);
  if (xiaolingVersion) validateIdentifier(xiaolingVersion, "Xiaoling version", 128);
  return {
    publicConfig: {
      baseUrl: normalizePlatformBaseUrl(stringValue(value.baseURL)),
      platformTokenSecretKey,
      ...(agentJsVersion ? { agentJsVersion } : {}),
      ...(agentBundleAppId ? { agentBundleAppId } : {}),
      ...(businessAppId ? { businessAppId, llmApp: businessAppId } : {}),
      ...(xiaolingVersion ? { xiaolingVersion } : {}),
      ...(features.length > 0 ? { features } : {}),
      nlu: publicNlu,
      tts: redactRecord(recordValue(value.ttsProperty)),
      runtime,
    },
    secrets,
    warnings: [...legacy.warnings, ...secretWarnings, ...validationWarnings],
  };
}

function normalizeFeatures(value: unknown): string[] {
  if (!Array.isArray(value)) return [];
  return Array.from(new Set(value
    .filter((item): item is string => typeof item === "string")
    .map((item) => item.trim())
    .filter(Boolean)))
    .slice(0, 32);
}

function summarizeToolSources(value: JsonValue[]): JsonValue[] {
  const output: JsonValue[] = [];
  for (const raw of value) {
    if (!isRecord(raw)) continue;
    const fn = isRecord(raw.function) ? raw.function : raw;
    const name = stringValue(fn.name);
    if (!name) continue;
    output.push({
      name,
      source: stringValue(raw.source),
      enabled: raw.enable !== false && raw.enabled !== false,
    });
  }
  return output;
}

function normalizeModelProvider(
  value: JsonValue | undefined,
  secretPrefix: string,
  secrets: Record<string, string>,
  secretNamespace: string,
): NormalizedModelProvider | undefined {
  if (value === undefined || value === null) return undefined;
  if (!isRecord(value)) throw new Error("Model provider must be an object");
  const type = stringValue(value.type);
  const model = stringValue(value.model);
  if (type === "platform") {
    requireOnlyKeys(value, ["type", "model"], "platform model provider");
    validateIdentifier(model, "Platform model", 256);
    return { type, model };
  }
  if (type !== "openai_compatible") throw new Error("Unsupported model provider type");
  requireOnlyKeys(
    value,
    ["type", "base_url", "api_key", "token", "model", "headers", "extra_body"],
    "custom model provider",
  );
  const baseUrl = stringValue(value.base_url);
  const apiKey = stringValue(value.api_key) || stringValue(value.token);
  if (!baseUrl || !apiKey || !model) throw new Error("Custom model URL, key, and model are required");
  validateIdentifier(model, "Custom model", 256);
  if (apiKey.length > 8_192 || hasControlCharacter(apiKey)) {
    throw new Error("Custom model API key is invalid");
  }
  const headers = validateCustomHeaders(value.headers);
  const extraBody = validateExtraBody(value.extra_body);
  const apiKeySecretKey = secretName(secretNamespace, `${secretPrefix}.api_key`);
  secrets[apiKeySecretKey] = apiKey;
  const normalized: OpenAICompatibleModelConfig = {
    type,
    baseUrl: normalizeHTTPURL(baseUrl, "Custom model URL", true),
    apiKeySecretKey,
    model,
  };
  if (Object.keys(headers).length > 0) {
    const headersSecretKey = secretName(secretNamespace, `${secretPrefix}.headers`);
    secrets[headersSecretKey] = JSON.stringify(headers);
    normalized.headersSecretKey = headersSecretKey;
  }
  if (Object.keys(extraBody).length > 0) normalized.extraBody = extraBody;
  return normalized;
}

function normalizeSidecars(
  source: JsonRecord,
  secrets: Record<string, string>,
  secretNamespace: string,
): Record<string, NormalizedModelProvider> {
  const output: Record<string, NormalizedModelProvider> = {};
  const allowed = new Set(["emotion", "preference", "memory", "vision"]);
  for (const [name, value] of Object.entries(source)) {
    validateIdentifier(name, "Sidecar name", 64);
    if (!allowed.has(name)) throw new Error("Unsupported model sidecar");
    const provider = normalizeModelProvider(value, `model.sidecars.${name}`, secrets, secretNamespace);
    if (provider) output[name] = provider;
  }
  return output;
}

function normalizeMCPServers(
  source: JsonRecord,
  secrets: Record<string, string>,
  secretNamespace: string,
  warnings: string[],
): JsonRecord {
  const output: JsonRecord = {};
  for (const [serverId, value] of Object.entries(source).slice(0, 16)) {
    try {
      validateIdentifier(serverId, "MCP server ID", 64);
      if (!isRecord(value)) throw new Error("MCP server must be an object");
      requireOnlyKeys(
        value,
        ["enabled", "transport", "transport_type", "url", "headers", "authorization"],
        "MCP server",
      );
      if (value.enabled !== undefined && typeof value.enabled !== "boolean") {
        throw new Error("MCP enabled must be boolean");
      }
      const transportValue = stringValue(value.transport) || stringValue(value.transport_type);
      const transport = normalizeMCPTransport(transportValue);
      const url = normalizeHTTPURL(stringValue(value.url), "MCP server URL", true);
      const headers = validateHeaderRecord(value.headers, true, "MCP headers");
      const authorization = stringValue(value.authorization);
      if (authorization && (hasControlCharacter(authorization) || utf8ByteLength(authorization) > 8_192)) {
        throw new Error("MCP authorization is invalid");
      }
      if (authorization && !hasHeader(headers, "authorization")) headers.Authorization = authorization;
      const secretHeadersRef = Object.keys(headers).length > 0
        ? secretName(secretNamespace, `mcp.${serverId}.headers`)
        : "";
      if (secretHeadersRef) secrets[secretHeadersRef] = JSON.stringify(headers);
      output[serverId] = {
        enabled: value.enabled !== false,
        transport,
        url,
        ...(secretHeadersRef ? { secretHeadersRef } : {}),
      };
    } catch {
      warnings.push(`mcp.invalid.disabled:${serverId.slice(0, 64) || "unknown"}`);
    }
  }
  if (Object.keys(source).length > 16) warnings.push("mcp.limit_exceeded");
  return output;
}

function normalizeToolDefinitions(source: JsonValue[], strict: boolean): JsonValue[] {
  const output: JsonValue[] = [];
  const names = new Set<string>();
  if (source.length > 128) throw new Error("Tool definitions exceed the 128-tool hard limit");
  for (const value of source) {
    if (!isRecord(value)) throw new Error("Tool definition must be an object");
    if (strict) requireOnlyKeys(value, ["type", "function", "source", "enable", "enabled"], "tool definition");
    if (value.type !== undefined && value.type !== "function") {
      throw new Error("Tool definition type must be function");
    }
    const fn = isRecord(value.function) ? value.function : value;
    if (strict) requireOnlyKeys(fn, ["name", "description", "parameters"], "tool function");
    const name = stringValue(fn.name);
    if (fn.parameters !== undefined && !isRecord(fn.parameters)) {
      throw new Error("Tool parameters must be an object schema");
    }
    if (fn.input_schema !== undefined && !isRecord(fn.input_schema)) {
      throw new Error("Tool input_schema must be an object schema");
    }
    const parameters = isRecord(fn.parameters)
      ? fn.parameters
      : isRecord(fn.input_schema)
        ? fn.input_schema
        : { type: "object", properties: {} };
    validateToolName(name);
    if (names.has(name)) throw new Error("Tool names must be unique");
    names.add(name);
    const description = stringValue(fn.description);
    if (utf8ByteLength(description) > 4_000) throw new Error("Tool description is too large");
    const definition = {
      type: "function",
      function: {
        name,
        ...(description ? { description } : {}),
        parameters: clone(parameters),
      },
    } as FunctionTool;
    validateFunctionToolDefinition(definition, { maxSchemaDepth: 12 });
    output.push(definition as unknown as JsonValue);
  }
  return output;
}

function normalizeLegacyToolBindings(
  source: JsonValue | undefined,
  secrets: Record<string, string>,
  secretNamespace: string,
): JsonRecord {
  if (!Array.isArray(source)) return {};
  const bindings: JsonRecord = {};
  for (const value of source) {
    if (!isRecord(value)) continue;
    const fn = isRecord(value.function) ? value.function : value;
    const name = stringValue(fn.name);
    if (!name) continue;
    if (isRecord(value.binding)) {
      bindings[name] = value.binding;
    } else if (stringValue(value.url)) {
      bindings[name] = {
        type: "http",
        url: stringValue(value.url),
        ...(isRecord(value.headers) ? { headers: value.headers } : {}),
      };
    } else if (stringValue(value.tool_id)) {
      bindings[name] = { type: "platform", tool_id: stringValue(value.tool_id) };
    } else if (stringValue(value.handler_id)) {
      bindings[name] = { type: "local", handler_id: stringValue(value.handler_id) };
    }
  }
  return normalizeToolBindings(bindings, secrets, secretNamespace, false);
}

function normalizeToolBindings(
  source: JsonRecord,
  secrets: Record<string, string>,
  secretNamespace: string,
  strict: boolean,
): JsonRecord {
  const output: JsonRecord = {};
  for (const [name, raw] of Object.entries(source)) {
    validateToolName(name);
    if (!isRecord(raw)) throw new Error("Tool binding must be an object");
    const type = stringValue(raw.type) || stringValue(raw.kind);
    if (type === "platform") {
      if (strict) requireOnlyKeys(raw, ["type", "tool_id", "timeout_ms", "quota_failure_policy"], "platform tool binding");
      const toolId = stringValue(raw.tool_id) || stringValue(raw.toolId);
      validateIdentifier(toolId, "Platform tool ID", 256);
      const timeoutMs = optionalBoundedNumber("timeout_ms", raw.timeout_ms ?? raw.timeoutMs, 1, 120_000, true);
      const quotaPolicy = stringValue(raw.quota_failure_policy ?? raw.quotaFailurePolicy);
      if (quotaPolicy && quotaPolicy !== "return_tool_error" && quotaPolicy !== "stop_turn") {
        throw new Error("Invalid platform tool quota failure policy");
      }
      output[name] = {
        type,
        tool_id: toolId,
        ...timeoutMs,
        ...(quotaPolicy ? { quota_failure_policy: quotaPolicy } : {}),
      };
      continue;
    }
    if (type === "device") {
      if (strict) requireOnlyKeys(raw, ["type", "protocol", "original_name", "timeout_ms"], "device tool binding");
      const originalName = stringValue(raw.original_name) || stringValue(raw.originalName) || name;
      const protocolValue = stringValue(raw.protocol) || "xiaoling";
      if (protocolValue !== "xiaoling" && protocolValue !== "xiaozhi") {
        throw new Error("Invalid device tool protocol");
      }
      validateIdentifier(originalName, "Device tool name", 256);
      output[name] = {
        type,
        protocol: protocolValue,
        original_name: originalName,
        ...optionalBoundedNumber("timeout_ms", raw.timeout_ms ?? raw.timeoutMs, 1, 120_000, true),
      };
      continue;
    }
    if (type === "http" || type === "custom_http") {
      if (strict && type !== "http") throw new Error("Unsupported canonical tool binding type");
      if (strict) requireOnlyKeys(raw, ["type", "url", "headers", "timeout_ms", "max_response_bytes"], "HTTP tool binding");
      const url = stringValue(raw.url);
      const normalizedURL = normalizeHTTPURL(url, "Custom tool URL", true);
      const headers = validateHeaderRecord(raw.headers, true, "Custom tool headers");
      const secretHeadersRef = Object.keys(headers).length > 0
        ? secretName(secretNamespace, `tool.${name}.headers`)
        : stringValue(raw.secret_headers_ref) || stringValue(raw.secretHeadersRef);
      if (Object.keys(headers).length > 0) secrets[secretHeadersRef] = JSON.stringify(headers);
      output[name] = {
        type: "http",
        url: normalizedURL,
        ...(secretHeadersRef ? { secret_headers_ref: secretHeadersRef } : {}),
        ...optionalBoundedNumber("timeout_ms", raw.timeout_ms ?? raw.timeoutMs, 1, 120_000, true),
        ...optionalBoundedNumber("max_response_bytes", raw.max_response_bytes ?? raw.maxResponseBytes, 1, 1 << 20, true),
      };
      continue;
    }
    if (type === "local") {
      if (strict) requireOnlyKeys(raw, ["type", "handler_id"], "local tool binding");
      const handlerId = stringValue(raw.handler_id) || stringValue(raw.handlerId);
      validateIdentifier(handlerId, "Local handler ID", 128);
      output[name] = { type, handler_id: handlerId };
      continue;
    }
    throw new Error("Unsupported tool binding type");
  }
  return output;
}

function normalizeReact(source: JsonRecord): NormalizedAgentRuntimeConfig["react"] {
  requireOnlyKeys(
    source,
    ["max_steps", "max_tool_calls", "duplicate_tool_calls", "tool_execution"],
    "agent_runtime.react",
  );
  if (source.duplicate_tool_calls !== undefined && source.duplicate_tool_calls !== "reject") {
    throw new Error("ReAct duplicate_tool_calls must be reject");
  }
  if (source.tool_execution !== undefined && source.tool_execution !== "serial") {
    throw new Error("ReAct tool_execution must be serial");
  }
  return {
    maxSteps: requiredBoundedInteger(source.max_steps, 10, 1, 20, "ReAct max_steps"),
    maxToolCalls: requiredBoundedInteger(source.max_tool_calls, 10, 0, 20, "ReAct max_tool_calls"),
    duplicateToolCalls: "reject",
    toolExecution: "serial",
  };
}

function validateBindingReferences(bindings: JsonRecord, definitions: JsonValue[]): void {
  const names = new Set<string>();
  for (const definition of definitions) {
    if (!isRecord(definition)) continue;
    const fn = recordValue(definition.function);
    const name = stringValue(fn.name);
    if (name) names.add(name);
  }
  for (const name of Object.keys(bindings)) {
    if (!names.has(name)) throw new Error(`Tool binding has no matching definition: ${name}`);
  }
}

function validateToolName(name: string): void {
  if (!/^[A-Za-z_][A-Za-z0-9_-]{0,63}$/.test(name)) {
    throw new Error("Tool name is invalid");
  }
}

const CUSTOM_HEADER_BLOCKLIST = new Set([
  "authorization",
  "host",
  "content-length",
  "connection",
  "transfer-encoding",
  "proxy-authorization",
  "x-agent-session-id",
  "x-agent-turn-id",
  "x-agent-tool-call-id",
  "x-model-call-id",
  "x-request-id",
  "traceparent",
  "tracestate",
]);

const EXTRA_BODY_ALLOWLIST = new Set([
  "top_p",
  "frequency_penalty",
  "presence_penalty",
  "seed",
  "response_format",
  "stop",
]);

function validateCustomHeaders(value: JsonValue | undefined): Record<string, string> {
  return validateHeaderRecord(value, false, "Custom model headers");
}

function validateHeaderRecord(
  value: JsonValue | undefined,
  allowAuthorization: boolean,
  label: string,
): Record<string, string> {
  if (value === undefined) return {};
  if (!isRecord(value)) throw new Error(`${label} must be an object`);
  if (Object.keys(value).length > 64) throw new Error(`${label} has too many entries`);
  const output: Record<string, string> = {};
  let totalBytes = 0;
  for (const [name, raw] of Object.entries(value)) {
    const lower = name.toLowerCase();
    if (!/^[!#$%&'*+.^_`|~0-9A-Za-z-]{1,128}$/.test(name)
      || (!allowAuthorization && CUSTOM_HEADER_BLOCKLIST.has(lower))
      || (allowAuthorization && CUSTOM_HEADER_BLOCKLIST.has(lower) && lower !== "authorization")) {
      throw new Error(`${label} contains a protected header`);
    }
    if (typeof raw !== "string" || hasControlCharacter(raw) || utf8ByteLength(raw) > 8_192) {
      throw new Error(`${label} contains an invalid value`);
    }
    totalBytes += utf8ByteLength(name) + utf8ByteLength(raw);
    if (totalBytes > 32 << 10) throw new Error(`${label} is too large`);
    output[name] = raw;
  }
  return output;
}

function validateExtraBody(value: JsonValue | undefined): JsonRecord {
  if (value === undefined) return {};
  if (!isRecord(value)) throw new Error("Custom model extra_body must be an object");
  for (const key of Object.keys(value)) {
    if (!EXTRA_BODY_ALLOWLIST.has(key)) throw new Error("Custom model extra_body contains a protected field");
  }
  if (utf8ByteLength(JSON.stringify(value)) > 16 << 10) {
    throw new Error("Custom model extra_body is too large");
  }
  return clone(value);
}

function normalizeMCPTransport(value: string): "streamable_http" | "sse" {
  if (value === "sse") return "sse";
  if (value === "" || value === "http" || value === "streamable-http" || value === "streamable_http") {
    return "streamable_http";
  }
  throw new Error("Unsupported MCP transport");
}

function redactNlu(nlu: JsonRecord): JsonRecord {
  const output = redactRecord(nlu);
  delete output.agent_runtime;
  delete output.mcp_servers;
  delete output.agent_tools;
  delete output.aiui_options;
  delete output.aiui_tools;
  if (isRecord(output.input)) {
    const input = clone(output.input);
    if (isRecord(input.netease_music)) {
      const music = clone(input.netease_music);
      delete music.access_token;
      delete music.netease_mode;
      input.netease_music = music;
    }
    output.input = input;
  }
  return output;
}

function extractLegacySecrets(
  nlu: JsonRecord,
  secrets: Record<string, string>,
  secretNamespace: string,
  warnings: string[],
): void {
  const input = recordValue(nlu.input);
  const music = recordValue(input.netease_music);
  const accessToken = stringValue(music.access_token);
  const mode = stringValue(music.netease_mode);
  if (mode && mode !== "guest") {
    warnings.push("legacy.netease_mode_invalid");
    return;
  }
  if (accessToken) {
    secrets[secretName(secretNamespace, "integration.netease_music")] = JSON.stringify({
      access_token: accessToken,
      ...(mode ? { mode } : {}),
    });
  }
}

function secretName(namespace: string, name: string): string {
  return namespace ? `${namespace}.${name}` : name;
}

function mergeRecords(...sources: JsonRecord[]): JsonRecord {
  const output: JsonRecord = {};
  for (const source of sources) {
    for (const [key, value] of Object.entries(source)) {
      if (isRecord(output[key]) && isRecord(value)) {
        output[key] = mergeRecords(output[key] as JsonRecord, value);
      } else if (value !== undefined) {
        output[key] = clone(value);
      }
    }
  }
  return output;
}

function redactRecord(source: JsonRecord): JsonRecord {
  const output: JsonRecord = {};
  for (const [key, value] of Object.entries(source)) {
    if (/(authorization|cookie|token|api[_-]?key|app[_-]?key|secret|password|credential)/i.test(key)) continue;
    if (isRecord(value)) output[key] = redactRecord(value);
    else if (Array.isArray(value)) output[key] = value.map((item) => isRecord(item) ? redactRecord(item) : item);
    else output[key] = value;
  }
  return output;
}

function hasHeader(headers: JsonRecord, target: string): boolean {
  return Object.keys(headers).some((key) => key.toLowerCase() === target.toLowerCase());
}

function normalizePlatformBaseUrl(value: string): string {
  return normalizeHTTPURL(value || "https://api.listenai.com", "Platform base URL", false);
}

function normalizeHTTPURL(value: string, label: string, allowInsecureHTTP: boolean): string {
  const normalized = value.trim().replace(/\/+$/, "");
  const match = /^(https?):\/\/(?:[A-Za-z0-9](?:[A-Za-z0-9.-]*[A-Za-z0-9])?|\[[0-9A-Fa-f:]+\])(?::[0-9]{1,5})?(?:\/[^\s]*)?$/.exec(normalized);
  if (normalized.length > 2_048
    || hasControlCharacter(normalized)
    || normalized.includes("#")
    || !match
    || (!allowInsecureHTTP && match[1] !== "https")) {
    throw new Error(`${label} is not allowed`);
  }
  const authority = normalized.slice(match[1].length + 3).split("/", 1)[0];
  const portMatch = /:([0-9]{1,5})$/.exec(authority);
  if (portMatch && Number(portMatch[1]) > 65_535) throw new Error(`${label} is not allowed`);
  return normalized;
}

function optionalBoundedNumber(
  key: string,
  value: JsonValue | undefined,
  minimum: number,
  maximum: number,
  integer: boolean,
): JsonRecord {
  if (value === undefined) return {};
  if (typeof value !== "number"
    || !Number.isFinite(value)
    || value < minimum
    || value > maximum
    || (integer && !Number.isInteger(value))) {
    throw new Error(`${key} is outside the supported range`);
  }
  return { [key]: value };
}

function requiredBoundedInteger(
  value: JsonValue | undefined,
  fallback: number,
  minimum: number,
  maximum: number,
  label: string,
): number {
  if (value === undefined) return fallback;
  if (typeof value !== "number"
    || !Number.isInteger(value)
    || value < minimum
    || value > maximum) {
    throw new Error(`${label} is outside the supported range`);
  }
  return value;
}

function requireOnlyKeys(value: JsonRecord, allowed: string[], label: string): void {
  const allowlist = new Set(allowed);
  if (Object.keys(value).some((key) => !allowlist.has(key))) {
    throw new Error(`${label} contains an unsupported field`);
  }
}

function requireOptionalRecord(value: JsonValue | undefined, label: string): void {
  if (value !== undefined && !isRecord(value)) throw new Error(`${label} must be an object`);
}

function validateIdentifier(value: string, label: string, maxBytes: number): void {
  if (!value || utf8ByteLength(value) > maxBytes || hasControlCharacter(value)) {
    throw new Error(`${label} is invalid`);
  }
}

function hasControlCharacter(value: string): boolean {
  return /[\u0000-\u001f\u007f]/.test(value);
}

function utf8ByteLength(value: string): number {
  let length = 0;
  for (const character of value) {
    const codePoint = character.codePointAt(0) ?? 0;
    length += codePoint <= 0x7f ? 1 : codePoint <= 0x7ff ? 2 : codePoint <= 0xffff ? 3 : 4;
  }
  return length;
}

function booleanRecord(value: JsonValue | undefined, strict = false): Record<string, boolean> {
  if (!isRecord(value)) return {};
  const output: Record<string, boolean> = {};
  const names: Record<string, string> = {
    text_to_image: "textToImage",
    image_to_text: "imageToText",
    long_memory: "longMemory",
  };
  const allowed = new Set([
    "search",
    "text_to_image",
    "image_to_text",
    "long_memory",
    "preferences",
    "aiui",
    "music",
    "full_duplex",
    "persona",
    "emotion",
    "device_control",
  ]);
  for (const [key, item] of Object.entries(value)) {
    if (strict && (!allowed.has(key) || typeof item !== "boolean")) {
      throw new Error("agent_runtime.capabilities contains an unsupported field");
    }
    if (typeof item === "boolean") output[names[key] ?? key] = item;
  }
  return output;
}

function numberValue(value: JsonValue | undefined): number | undefined {
  return typeof value === "number" && Number.isFinite(value) ? value : undefined;
}

function stringValue(value: JsonValue | undefined): string {
  return typeof value === "string" ? value.trim() : "";
}

function recordValue(value: JsonValue | undefined): JsonRecord {
  return isRecord(value) ? value : {};
}

function isRecord(value: unknown): value is JsonRecord {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function clone<T>(value: T): T {
  return JSON.parse(JSON.stringify(value)) as T;
}
