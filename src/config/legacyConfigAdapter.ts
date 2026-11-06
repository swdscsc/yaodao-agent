import type { JsonRecord, NormalizedAgentRuntimeConfig } from "./schema";

export const OFFICIAL_DEFAULT_MODEL = "deepseek-v4-flash";
export const OFFICIAL_DEFAULT_VISION_MODEL = "ls-interaction-img2txt-v2";

export interface LegacyAdaptation {
  runtime: Partial<NormalizedAgentRuntimeConfig>;
  warnings: string[];
}

export function adaptLegacyConfig(nlu: JsonRecord): LegacyAdaptation {
  const runtime: Partial<NormalizedAgentRuntimeConfig> = {};
  const warnings: string[] = [];
  const modelName = stringValue(nlu.agent_model);
  if (modelName && stringValue(nlu.interaction_model) !== "ls-xiaoling") {
    runtime.model = {
      primary: { type: "platform", model: modelName },
    };
    warnings.push("legacy.agent_model");
  }
  if (nlu.agent_model_fallback_enable === true) {
    runtime.model = {
      ...(runtime.model ?? { primary: { type: "platform", model: OFFICIAL_DEFAULT_MODEL } }),
      fallback: { type: "platform", model: OFFICIAL_DEFAULT_MODEL },
    };
    warnings.push("legacy.agent_model_fallback_enable");
  }
  if (nlu.img2text_enable === true) {
    const current = runtime.model ?? {
      primary: { type: "platform" as const, model: OFFICIAL_DEFAULT_MODEL },
    };
    runtime.model = {
      ...current,
      sidecars: {
        ...(current.sidecars ?? {}),
        vision: { type: "platform", model: OFFICIAL_DEFAULT_VISION_MODEL },
      },
    };
    warnings.push("legacy.img2text_model");
  }
  if (Array.isArray(nlu.agent_tools)) {
    runtime.tools = clone(nlu.agent_tools);
    warnings.push("legacy.agent_tools");
  }
  if (isRecord(nlu.mcp_servers)) {
    runtime.mcpServers = clone(nlu.mcp_servers);
    warnings.push("legacy.mcp_servers");
  }
  const capabilities: Record<string, boolean> = {};
  for (const [legacy, canonical] of [
    ["search_enable", "search"],
    ["text2img_enable", "textToImage"],
    ["img2text_enable", "imageToText"],
    ["long_memory_enable", "longMemory"],
    ["long_memory_enable_v2", "longMemoryV2"],
    ["favor_enable", "preferences"],
  ] as const) {
    if (typeof nlu[legacy] === "boolean") capabilities[canonical] = nlu[legacy] as boolean;
  }
  if (typeof nlu.aiui_domain === "boolean") capabilities.aiui = nlu.aiui_domain;
  if (Object.keys(capabilities).length > 0) {
    runtime.capabilities = capabilities;
    warnings.push("legacy.capabilities");
  }
  runtime.legacyPolicy = {
    toolRewrite: recordValue(nlu.agent_tools_rewrite),
    toolSchemaOverride: Array.isArray(nlu.agent_tools_schema_override)
      ? clone(nlu.agent_tools_schema_override)
      : [],
    disabledTools: Array.isArray(nlu.agent_tools_fillter) ? clone(nlu.agent_tools_fillter) : [],
    appSource: stringValue(nlu.app_source),
    toolSources: summarizeToolSources(nlu.agent_tools),
    dsa: nlu.dsa === true,
    useHDImage: nlu.use_hd_image === true,
    toolProtocolVersion: stringValue(nlu.tool_protocol_version) || "v2",
    agentVersion: stringValue(nlu.agent_version),
    x6Tag: nlu.x6_tag !== false,
    memoryVersion: nlu.long_memory_enable_v2 === false ? "v1" : "v2",
    preferenceVersion: stringValue(nlu.favor_version) === "v2" ? "v2" : "v1",
  };
  return { runtime, warnings };
}

function summarizeToolSources(value: unknown): Array<{ name: string; source: string; enabled: boolean }> {
  if (!Array.isArray(value)) return [];
  const output: Array<{ name: string; source: string; enabled: boolean }> = [];
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

function stringValue(value: unknown): string {
  return typeof value === "string" ? value.trim() : "";
}

function recordValue(value: unknown): JsonRecord {
  return isRecord(value) ? clone(value) : {};
}

function isRecord(value: unknown): value is JsonRecord {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function clone<T>(value: T): T {
  return JSON.parse(JSON.stringify(value)) as T;
}
