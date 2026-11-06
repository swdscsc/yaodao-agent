import { truncateUtf8 } from "../text/utf8Budget";
import type { ServerDsaPolicy } from "./toolPolicies";

const MAX_DSA_PROMPT_BYTES = 64 << 10;

export function disabledServerDsaPolicy(): ServerDsaPolicy {
  return { enabled: false, systemPrompt: "", allowedToolIds: [] };
}

export function parseServerDsaPolicy(productConfig: unknown): ServerDsaPolicy {
  const product = record(productConfig);
  const runtimePolicy = record(product.runtime_policy);
  const dsa = record(runtimePolicy.dsa);
  if (dsa.enabled !== true || typeof dsa.system_prompt !== "string") {
    return disabledServerDsaPolicy();
  }
  const systemPrompt = truncateUtf8(dsa.system_prompt.trim(), MAX_DSA_PROMPT_BYTES);
  const allowedToolIds = Array.isArray(dsa.allowed_tool_ids)
    ? Array.from(new Set(dsa.allowed_tool_ids
      .filter((value): value is string => (
        typeof value === "string"
        && /^platform\.dsa\.[A-Za-z0-9._:-]{1,128}$/.test(value)
      ))))
      .slice(0, 64)
    : [];
  return systemPrompt && allowedToolIds.length > 0
    ? { enabled: true, systemPrompt, allowedToolIds }
    : disabledServerDsaPolicy();
}

function record(value: unknown): Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value)
    ? value as Record<string, unknown>
    : {};
}
