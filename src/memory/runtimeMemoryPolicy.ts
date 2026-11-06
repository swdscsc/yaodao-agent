import {
  AgentError,
  type AgentRuntimeMemoryPolicy,
} from "@listenai/agent-sdk";

const MEMORY_POLICY_KEYS = new Set([
  "recall_enabled",
  "store_enabled",
  "preferences_enabled",
  "subject_strategy",
]);

export function disabledRuntimeMemoryPolicy(): AgentRuntimeMemoryPolicy {
  return {
    recall_enabled: false,
    store_enabled: false,
    preferences_enabled: false,
    subject_strategy: "voice_profile_then_vpr_group",
  };
}

export function parseRuntimeMemoryPolicy(productConfig: unknown): AgentRuntimeMemoryPolicy {
  const product = record(productConfig);
  const runtimePolicy = record(product.runtime_policy);
  const memory = record(runtimePolicy.memory);
  const exactKeys = Object.keys(memory).every((key) => MEMORY_POLICY_KEYS.has(key));
  if (!exactKeys
    || typeof memory.recall_enabled !== "boolean"
    || typeof memory.store_enabled !== "boolean"
    || typeof memory.preferences_enabled !== "boolean"
    || memory.subject_strategy !== "voice_profile_then_vpr_group") {
    throw new AgentError("AGENT_RESPONSE_INVALID", "Prepared memory policy is invalid", {
      phase: "transport",
    });
  }
  return {
    recall_enabled: memory.recall_enabled,
    store_enabled: memory.store_enabled,
    preferences_enabled: memory.preferences_enabled,
    subject_strategy: memory.subject_strategy,
  };
}

function record(value: unknown): Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value)
    ? value as Record<string, unknown>
    : {};
}
