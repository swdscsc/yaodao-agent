import { safeMCPToolAlias } from "@listenai/agent-sdk";
import type { DeviceCapability, FunctionTool, ToolChoice } from "@listenai/agent-sdk";

export interface ToolSources {
  tools?: FunctionTool[];
  toolBindings?: Record<string, unknown>;
  mcpServers?: Record<string, unknown>;
}

export interface NormalizedToolSources {
  definitions: FunctionTool[];
  bindings: Record<string, unknown>;
  mcpServers: Record<string, unknown>;
}

export interface ToolPolicyInput {
  explicitDefinitions?: FunctionTool[];
  explicitBindings?: Record<string, unknown>;
  configuredDefinitions: FunctionTool[];
  configuredBindings: Record<string, unknown>;
  platformDefinitions: FunctionTool[];
  platformBindings: Record<string, unknown>;
  deviceCapabilities: DeviceCapability[];
  mcpTools?: MCPPolicyTool[];
  localDefaults?: Array<{ definition: FunctionTool; binding: unknown }>;
  capabilities: Record<string, boolean>;
  legacyPolicy: Record<string, unknown>;
  mcpServers: Record<string, unknown>;
  openclawCapabilities?: Record<string, unknown>;
  dsaPolicy?: ServerDsaPolicy;
}

export interface MCPPolicyTool {
  serverId: string;
  originalName: string;
  definition: FunctionTool;
}

export interface ServerDsaPolicy {
  enabled: boolean;
  systemPrompt: string;
  allowedToolIds: string[];
}

export interface ToolPolicyResult extends NormalizedToolSources {
  toolChoice: ToolChoice;
  warnings: string[];
}

const CAPABILITY_GATES: Array<{ names: Set<string>; keys: string[] }> = [
  { names: new Set(["online_realtime_search"]), keys: ["search"] },
  { names: new Set(["draw_image", "edit_image", "my_image"]), keys: ["text_to_image", "textToImage"] },
  { names: new Set(["play_music", "play_general_music", "play_kuwo_music", "play_audio_link"]), keys: ["music"] },
  { names: new Set(["switch_full_duplex", "switch_full_duplex_v2"]), keys: ["full_duplex", "fullDuplex"] },
  { names: new Set(["model_persona_update"]), keys: ["persona"] },
  { names: new Set(["set_emotion"]), keys: ["emotion"] },
  { names: new Set(["hood_set_speed"]), keys: ["device_control", "deviceControl"] },
];

const OPENCLAW_CAPABILITIES: Record<string, string> = {
  openclaw_chat: "chat_enable",
  set_emotion: "chat_enable",
  spoken_content: "chat_enable",
  manage_memo: "memo_enable",
  manage_reminders: "alarm_enable",
  alarm_clock: "alarm_enable",
  take_photo: "photo_enable",
  draw_image: "image_enable",
  edit_image: "image_enable",
  online_realtime_search: "realtime_enable",
  get_holiday_info: "realtime_enable",
  get_weather_info: "realtime_enable",
};

const OPENCLAW_DISPATCHERS: Record<string, string> = {
  chat_enable: "openclaw_chat",
  memo_enable: "openclaw_memo",
  alarm_enable: "openclaw_alarm",
  photo_enable: "openclaw_photo",
  image_enable: "openclaw_image",
  realtime_enable: "openclaw_realtime",
};

const PROTECTED_PLATFORM_TOOL_NAMES = new Set([
  ...CAPABILITY_GATES.flatMap((gate) => Array.from(gate.names)),
  ...Object.keys(OPENCLAW_CAPABILITIES),
  ...Object.values(OPENCLAW_DISPATCHERS),
  "draw_image_hd",
  "media_agent_bridge",
  "spoken_content",
]);

export function normalizeToolSources(source: ToolSources): NormalizedToolSources {
  const definitions = (source.tools ?? []).map(cloneDefinition);
  return {
    definitions,
    bindings: clone(source.toolBindings ?? {}),
    mcpServers: clone(source.mcpServers ?? {}),
  };
}

export function applyToolPolicies(input: ToolPolicyInput): ToolPolicyResult {
  const definitions = new Map<string, FunctionTool>();
  const bindings = new Map<string, unknown>();
  const order: string[] = [];
  const warnings: string[] = [];
  const sourcePolicy = readToolSources(input.legacyPolicy.toolSources);
  const lowcode = string(input.legacyPolicy.appSource) === "lowcode";
  const disabledNames = new Set(readStringArray(input.legacyPolicy.disabledTools));

  const add = (definition: FunctionTool, binding: unknown, replace = false): void => {
    const name = definition.function.name;
    if (!definitions.has(name)) order.push(name);
    if (replace || !definitions.has(name)) definitions.set(name, cloneDefinition(definition));
    if (binding !== undefined && (replace || !bindings.has(name))) bindings.set(name, clone(binding));
  };

  for (const definition of input.explicitDefinitions ?? []) {
    add(definition, input.explicitBindings?.[definition.function.name]);
  }

  for (const definition of input.configuredDefinitions) {
    const name = definition.function.name;
    const policy = sourcePolicy.get(name);
    if (lowcode && policy && policy.enabled === false) continue;
    add(definition, input.configuredBindings[name]);
  }

  for (const definition of input.platformDefinitions) {
    const name = definition.function.name;
    const platformBinding = input.platformBindings[name];
    if (platformBinding === undefined) continue;
    const source = sourcePolicy.get(name);
    const lowcodeBuiltinOverride = lowcode && source?.source === "xiaoling" && source.enabled;
    if (lowcodeBuiltinOverride && definitions.has(name)) {
      bindings.set(name, clone(platformBinding));
      continue;
    }
    if (definitions.has(name)) {
      if (isProtectedPlatformCatalogEntry(name, platformBinding)) add(definition, platformBinding, true);
      continue;
    }
    add(definition, platformBinding);
  }

  for (const capability of input.deviceCapabilities) {
    const parsed = readDeviceCapability(capability);
    if (!parsed) {
      warnings.push("device_capability_invalid");
      continue;
    }
    const used = new Set(definitions.keys());
    const alias = used.has(parsed.alias)
      ? uniqueDeviceAlias(parsed.alias, parsed.originalName, used)
      : parsed.alias;
    const definition = cloneDefinition(parsed.definition);
    definition.function.name = alias;
    add(definition, {
      type: "device",
      protocol: parsed.protocol,
      original_name: parsed.originalName,
    });
  }

  const usedMCPNames = new Set([...definitions.keys(), ...PROTECTED_PLATFORM_TOOL_NAMES]);
  for (const candidate of input.mcpTools ?? []) {
    const unqualifiedName = safeMCPToolAlias(candidate.serverId, candidate.originalName, new Set());
    if (PROTECTED_PLATFORM_TOOL_NAMES.has(unqualifiedName)) {
      warnings.push(`mcp:${candidate.serverId}:protected_name`);
      continue;
    }
    if (disabledNames.has(candidate.originalName) || disabledNames.has(unqualifiedName)) continue;
    const alias = safeMCPToolAlias(candidate.serverId, candidate.originalName, usedMCPNames);
    usedMCPNames.add(alias);
    const definition = cloneDefinition(candidate.definition);
    definition.function.name = alias;
    add(definition, {
      type: "mcp",
      server_id: candidate.serverId,
      original_name: candidate.originalName,
    });
  }

  for (const item of input.localDefaults ?? []) add(item.definition, item.binding);

  applyNeteaseMusicBinding(bindings, input.legacyPolicy);
  applyHDImageBindingGate(definitions, bindings, input.legacyPolicy);

  applyCapabilityGates(definitions, bindings, input.capabilities);
  applySchemaAndDescriptionOverrides(definitions, input.legacyPolicy, warnings);
  removeNames(definitions, bindings, Array.from(disabledNames));
  applySystemMCPGates(definitions, bindings, input.mcpServers);

  applyServerDsaPolicy(definitions, bindings, input);

  const cloudAbility = readCloudAbility(input.openclawCapabilities);
  const dispatchBindings: Record<string, unknown> = {};
  for (const [ability, dispatcher] of Object.entries(OPENCLAW_DISPATCHERS)) {
    const binding = bindings.get(dispatcher);
    if (bindingSource(binding) === "openclaw_cloud") dispatchBindings[ability] = clone(binding);
    if (dispatcher !== "openclaw_chat") remove(definitions, bindings, dispatcher);
  }
  for (const name of Array.from(definitions.keys())) {
    const ability = OPENCLAW_CAPABILITIES[name];
    if (!ability) continue;
    if (cloudAbility[ability] === true && dispatchBindings[ability] !== undefined) {
      bindings.set(name, clone(dispatchBindings[ability]));
      continue;
    }
    if (name === "openclaw_chat" && bindingSource(bindings.get(name)) === "openclaw_cloud") {
      remove(definitions, bindings, name);
    }
  }

  for (const name of Array.from(definitions.keys())) {
    if (!bindings.has(name)) remove(definitions, bindings, name);
  }
  const finalNames = order.filter((name) => definitions.has(name));
  if (finalNames.length > 128) throw new Error("Tool policy exceeds the 128-tool hard limit");
  const outputBindings: Record<string, unknown> = {};
  for (const name of finalNames) outputBindings[name] = clone(bindings.get(name));
  const chatDelegated = cloudAbility.chat_enable === true
    && finalNames.includes("openclaw_chat")
    && bindingSource(bindings.get("openclaw_chat")) === "openclaw_cloud";
  return {
    definitions: finalNames.map((name) => cloneDefinition(definitions.get(name)!)),
    bindings: outputBindings,
    mcpServers: input.dsaPolicy?.enabled === true ? {} : clone(input.mcpServers),
    toolChoice: chatDelegated ? "required" : "auto",
    warnings,
  };
}

function applyServerDsaPolicy(
  definitions: Map<string, FunctionTool>,
  bindings: Map<string, unknown>,
  input: ToolPolicyInput,
): void {
  if (input.dsaPolicy?.enabled !== true) return;
  const allowed = new Set(input.dsaPolicy.allowedToolIds.slice(0, 64));
  const catalogDefinitions = new Map(
    input.platformDefinitions.map((definition) => [definition.function.name, definition]),
  );
  for (const name of Array.from(definitions.keys())) {
    const trustedDefinition = catalogDefinitions.get(name);
    const trustedBinding = record(input.platformBindings[name]);
    const toolId = string(trustedBinding.tool_id);
    if (!trustedDefinition || trustedBinding.type !== "platform" || !allowed.has(toolId)) {
      remove(definitions, bindings, name);
      continue;
    }
    definitions.set(name, cloneDefinition(trustedDefinition));
    bindings.set(name, clone(trustedBinding));
  }
}

function applyHDImageBindingGate(
  definitions: Map<string, FunctionTool>,
  bindings: Map<string, unknown>,
  legacyPolicy: Record<string, unknown>,
): void {
  if (legacyPolicy.useHDImage !== true) return;
  const binding = record(bindings.get("draw_image"));
  if (binding.type === "platform" && binding.tool_id === "platform.system.draw_image_hd") return;
  remove(definitions, bindings, "draw_image");
}

function applyNeteaseMusicBinding(
  bindings: Map<string, unknown>,
  legacyPolicy: Record<string, unknown>,
): void {
  const policy = record(legacyPolicy.neteaseMusic);
  const secretRef = string(policy.secretRef);
  if (policy.enabled !== true || !/^[A-Za-z0-9._:-]{1,256}$/.test(secretRef)) return;
  const binding = record(bindings.get("media_agent_bridge"));
  if (binding.type !== "platform" || binding.tool_id !== "platform.system.media_agent_bridge") return;
  bindings.set("media_agent_bridge", {
    ...binding,
    server_context: {
      type: "netease_music",
      secret_ref: secretRef,
    },
  });
}

function applyCapabilityGates(
  definitions: Map<string, FunctionTool>,
  bindings: Map<string, unknown>,
  capabilities: Record<string, boolean>,
): void {
  for (const gate of CAPABILITY_GATES) {
    if (!gate.keys.some((key) => capabilities[key] === false)) continue;
    for (const name of gate.names) remove(definitions, bindings, name);
  }
}

function applySchemaAndDescriptionOverrides(
  definitions: Map<string, FunctionTool>,
  policy: Record<string, unknown>,
  warnings: string[],
): void {
  const overrides = Array.isArray(policy.toolSchemaOverride) ? policy.toolSchemaOverride : [];
  if (overrides.length === 0) {
    const rewrites = record(policy.toolRewrite);
    for (const [name, value] of Object.entries(rewrites)) {
      const definition = definitions.get(name);
      if (definition && typeof value === "string" && value.trim()) {
        definition.function.description = value.trim();
      }
    }
    return;
  }
  for (const raw of overrides) {
    const override = record(raw);
    const fn = record(override.function);
    const name = string(fn.name);
    const definition = definitions.get(name);
    const parameters = record(fn.parameters);
    if (!name || !definition || parameters.type !== "object") {
      warnings.push(`schema_override_skipped:${name || "unknown"}`);
      continue;
    }
    if (override.replace === true) {
      definition.function.parameters = clone(parameters);
      if (typeof fn.description === "string" && fn.description.trim()) {
        definition.function.description = fn.description.trim();
      }
      continue;
    }
    if (schemaStructure(definition.function.parameters) !== schemaStructure(parameters)) {
      warnings.push(`schema_override_incompatible:${name}`);
      continue;
    }
    copyDescriptions(definition.function.parameters, parameters);
    if (typeof fn.description === "string" && fn.description.trim()) {
      definition.function.description = fn.description.trim();
    }
  }
}

function applySystemMCPGates(
  definitions: Map<string, FunctionTool>,
  bindings: Map<string, unknown>,
  servers: Record<string, unknown>,
): void {
  for (const [serverId, value] of Object.entries(servers)) {
    const server = record(value);
    if (server.enabled !== false) continue;
    const ids = [serverId, string(server.server_id)];
    for (const id of ids) {
      const match = /^__system_mcp_(.+)__$/.exec(id);
      if (match) remove(definitions, bindings, match[1]);
    }
  }
}

function readDeviceCapability(value: unknown): {
  alias: string;
  originalName: string;
  protocol: "xiaoling" | "xiaozhi";
  definition: FunctionTool;
} | undefined {
  const source = record(value);
  const definition = record(source.definition);
  const fn = record(definition.function);
  const alias = safeName(string(source.alias) || string(fn.name));
  const originalName = string(source.original_name);
  if (!alias || !originalName || definition.type !== "function" || record(fn.parameters).type !== "object") return undefined;
  return {
    alias,
    originalName,
    protocol: source.protocol === "xiaozhi" ? "xiaozhi" : "xiaoling",
    definition: definition as unknown as FunctionTool,
  };
}

function uniqueDeviceAlias(alias: string, originalName: string, used: Set<string>): string {
  const suffix = shortHash(originalName);
  const base = `device_${safeName(alias) || "tool"}`;
  let candidate = `${base.slice(0, 55 - suffix.length)}_${suffix}`;
  let index = 1;
  while (used.has(candidate)) {
    const numbered = `_${index++}`;
    candidate = `${base.slice(0, 64 - suffix.length - numbered.length - 1)}_${suffix}${numbered}`;
  }
  return candidate;
}

function readToolSources(value: unknown): Map<string, { source: string; enabled: boolean }> {
  const output = new Map<string, { source: string; enabled: boolean }>();
  if (!Array.isArray(value)) return output;
  for (const raw of value) {
    const item = record(raw);
    const name = string(item.name);
    if (name) output.set(name, { source: string(item.source), enabled: item.enabled !== false });
  }
  return output;
}

function readCloudAbility(value: Record<string, unknown> | undefined): Record<string, boolean> {
  const root = record(value);
  const nested = record(root.cloud_ability);
  const source = Object.keys(nested).length > 0 ? nested : root;
  const output: Record<string, boolean> = {};
  for (const key of Object.values(OPENCLAW_CAPABILITIES)) output[key] = source[key] === true;
  return output;
}

function bindingSource(value: unknown): string {
  return string(record(value).source);
}

function isProtectedPlatformCatalogEntry(name: string, value: unknown): boolean {
  const binding = record(value);
  return binding.type === "platform"
    && (PROTECTED_PLATFORM_TOOL_NAMES.has(name) || string(binding.source) === "platform_system");
}

function schemaStructure(value: unknown): string {
  return JSON.stringify(canonical(value, true));
}

function canonical(value: unknown, stripDescription: boolean): unknown {
  if (Array.isArray(value)) return value.map((item) => canonical(item, stripDescription));
  if (!isRecord(value)) return value;
  const output: Record<string, unknown> = {};
  for (const key of Object.keys(value).sort()) {
    if (stripDescription && key === "description") continue;
    output[key] = canonical(value[key], stripDescription);
  }
  return output;
}

function copyDescriptions(target: Record<string, unknown>, source: Record<string, unknown>): void {
  if (typeof source.description === "string") target.description = source.description;
  const targetProperties = record(target.properties);
  const sourceProperties = record(source.properties);
  for (const [name, sourceValue] of Object.entries(sourceProperties)) {
    const targetValue = targetProperties[name];
    if (isRecord(targetValue) && isRecord(sourceValue)) copyDescriptions(targetValue, sourceValue);
  }
  if (isRecord(target.items) && isRecord(source.items)) copyDescriptions(target.items, source.items);
}

function removeNames(
  definitions: Map<string, FunctionTool>,
  bindings: Map<string, unknown>,
  names: string[],
): void {
  for (const name of names) remove(definitions, bindings, name);
}

function remove(definitions: Map<string, FunctionTool>, bindings: Map<string, unknown>, name: string): void {
  definitions.delete(name);
  bindings.delete(name);
}

function cloneDefinition(value: FunctionTool): FunctionTool {
  return {
    type: "function",
    function: {
      name: value.function.name,
      ...(value.function.description ? { description: value.function.description } : {}),
      parameters: clone(value.function.parameters),
    },
  };
}

function readStringArray(value: unknown): string[] {
  return Array.isArray(value) ? value.filter((item): item is string => typeof item === "string") : [];
}

function safeName(value: string): string {
  return value.replace(/[^A-Za-z0-9_-]/g, "_").replace(/_+/g, "_").replace(/^_+|_+$/g, "").slice(0, 64);
}

function shortHash(value: string): string {
  let hash = 2166136261;
  for (let index = 0; index < value.length; index += 1) {
    hash ^= value.charCodeAt(index);
    hash = Math.imul(hash, 16777619);
  }
  return (hash >>> 0).toString(36).slice(0, 7);
}

function string(value: unknown): string {
  return typeof value === "string" ? value.trim() : "";
}

function record(value: unknown): Record<string, unknown> {
  return isRecord(value) ? value : {};
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function clone<T>(value: T): T {
  return JSON.parse(JSON.stringify(value)) as T;
}
