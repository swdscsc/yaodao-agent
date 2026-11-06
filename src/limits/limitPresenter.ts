import {
  AgentRuntimeClient,
  log,
  type AgentError,
  type AgentFeature,
} from "@listenai/agent-sdk";
import { requestContext, type VoiceTurnContext } from "../types";
import { safeErrorFields } from "../errors/safeLogging";

export const QUOTA_ERROR_CODES = new Set([
  "AGENT_CHAT_QUOTA_EXCEEDED",
  "AGENT_CAPABILITY_QUOTA_EXCEEDED",
]);

export function isQuotaErrorCode(code: string): boolean {
  return QUOTA_ERROR_CODES.has(code);
}

export interface QuotaErrorLike {
  code: string;
  message: string;
  publicDetails?: Record<string, unknown>;
}

export interface LimitPresentation {
  code: "AGENT_CHAT_QUOTA_EXCEEDED" | "AGENT_CAPABILITY_QUOTA_EXCEEDED";
  message: string;
}

export interface LimitPresenter {
  presentation(error: QuotaErrorLike): LimitPresentation | null;
  present(error: AgentError, context: VoiceTurnContext): Promise<LimitPresentation | null>;
}

export class DefaultLimitPresenter implements LimitPresenter {
  presentation(error: QuotaErrorLike): LimitPresentation | null {
    if (!isQuotaErrorCode(error.code)) return null;
    return {
      code: error.code as LimitPresentation["code"],
      message: error.message,
    };
  }

  async present(error: AgentError, context: VoiceTurnContext): Promise<LimitPresentation | null> {
    const presentation = this.presentation(error);
    if (!presentation) return null;
    const feature = quotaFeature(error);
    const sourceCode = quotaSourceCode(error);
    if (!feature || !sourceCode) return presentation;
    const client = new AgentRuntimeClient({
      baseUrl: context.config.baseUrl,
      tokenSecretKey: context.config.platformTokenSecretKey,
    });
    try {
      const action = await client.getUpgradeAction(
        feature,
        sourceCode,
        requestContext(context, "upgrade-action"),
        context.cancellation,
      );
      if (isRecord(action.action) && (action.action.type === "qrcode" || action.action.type === "link")) {
        await client.dispatchDeviceAction({
          action: "show_upgrade",
          feature,
          code: sourceCode,
        }, requestContext(context, "upgrade-dispatch"), context.cancellation);
      }
    } catch (actionError) {
      log.warn("quota upgrade action unavailable", {
        turnId: context.turnId,
        code: error.code,
        ...safeErrorFields(actionError),
      });
    }
    return presentation;
  }
}

function quotaSourceCode(error: AgentError): string | null {
  const sourceCode = error.publicDetails?.source_code;
  return typeof sourceCode === "string" && /^[A-Za-z][A-Za-z0-9._:-]{0,127}$/.test(sourceCode)
    ? sourceCode
    : null;
}

function quotaFeature(error: AgentError): AgentFeature | null {
  if (error.code === "AGENT_CHAT_QUOTA_EXCEEDED") return "chat";
  const feature = error.publicDetails?.feature;
  return typeof feature === "string" && isAgentFeature(feature) ? feature : null;
}

function isAgentFeature(value: string): value is AgentFeature {
  return [
    "chat", "vpr", "voice_clone", "voice_base", "voice_premium",
    "vision", "search", "drawing", "drawing_hd",
    "music", "favor", "memory", "wakeup_word", "knowledge_document",
  ].includes(value);
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}
