import {
  AgentError,
  OpenAICompatibleChatModel,
  PlatformChatModel,
  type ChatModel,
  type ModelFallbackPolicy,
} from "@listenai/agent-sdk";
import type {
  NormalizedModelProvider,
  OpenAICompatibleModelConfig,
} from "../config/schema";
import type { VoiceTurnContext } from "../types";

// The production/development HTTP decision belongs to the Host egress policy.
const DEFER_HTTP_POLICY_TO_HOST = true;

export interface ResolvedModel {
  model: ChatModel;
  modelName: string;
  fallback?: ModelFallbackPolicy;
}

export interface ModelResolver {
  resolve(context: VoiceTurnContext): ResolvedModel;
  resolveProvider(context: VoiceTurnContext, provider: NormalizedModelProvider): {
    model: ChatModel;
    modelName: string;
  };
}

export class ConfigModelResolver implements ModelResolver {
  resolve(context: VoiceTurnContext): ResolvedModel {
    const config = context.config.runtime.model;
    const primary = this.resolveProvider(context, config.primary);
    const fallbackCandidate = config.fallback
      ? this.resolveProvider(context, config.fallback)
      : undefined;
    const maxRetries = boundedRetries(config.maxRetries);
    const fallback = maxRetries > 0 || fallbackCandidate
      ? {
          maxPrimaryAttempts: maxRetries + 1,
          ...(fallbackCandidate ? { fallback: fallbackCandidate } : {}),
        }
      : undefined;
    return { ...primary, ...(fallback ? { fallback } : {}) };
  }

  resolveProvider(context: VoiceTurnContext, provider: NormalizedModelProvider): {
    model: ChatModel;
    modelName: string;
  } {
    if (provider.type === "platform") {
      return {
        model: new PlatformChatModel({
          baseUrl: context.config.baseUrl,
          tokenSecretKey: context.config.platformTokenSecretKey,
        }),
        modelName: provider.model,
      };
    }
    return {
      model: new OpenAICompatibleChatModel({
        id: `custom:${provider.model}`,
        baseUrl: provider.baseUrl,
        apiKeySecretKey: provider.apiKeySecretKey,
        model: provider.model,
        allowInsecureHttp: DEFER_HTTP_POLICY_TO_HOST,
        headers: readCustomHeaders(context.sessionId, provider),
        extraBody: provider.extraBody,
      }),
      modelName: provider.model,
    };
  }
}

function readCustomHeaders(
  sessionId: string,
  config: OpenAICompatibleModelConfig,
): Record<string, string> | undefined {
  if (!config.headersSecretKey) return undefined;
  const raw = host.secretGet(sessionId, config.headersSecretKey);
  if (!raw) throw new AgentError("AGENT_MODEL_CONFIG_INVALID", "Custom model headers are unavailable", {
    phase: "config",
  });
  let value: unknown;
  try {
    value = JSON.parse(raw) as unknown;
  } catch {
    throw new AgentError("AGENT_MODEL_CONFIG_INVALID", "Custom model headers are invalid", {
      phase: "config",
    });
  }
  if (!isStringRecord(value)) {
    throw new AgentError("AGENT_MODEL_CONFIG_INVALID", "Custom model headers are invalid", {
      phase: "config",
    });
  }
  return value;
}

function isStringRecord(value: unknown): value is Record<string, string> {
  return typeof value === "object"
    && value !== null
    && !Array.isArray(value)
    && Object.values(value).every((item) => typeof item === "string");
}

function boundedRetries(value?: number): number {
  if (!Number.isInteger(value) || Number(value) < 0) return 0;
  return Math.min(Number(value), 3);
}
