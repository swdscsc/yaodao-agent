import {
  AGENT_RUNTIME_CONTRACT_VERSION,
  AgentError,
  AgentRuntimeClient,
  type PrepareTurnResponse,
} from "@listenai/agent-sdk";
import { requestContext, type VoiceTurnContext } from "../types";

export interface ContextProvider {
  prepare(context: VoiceTurnContext): Promise<PrepareTurnResponse>;
}

export class ListenAIContextProvider implements ContextProvider {
  async prepare(context: VoiceTurnContext): Promise<PrepareTurnResponse> {
    const client = runtimeClient(context);
    const locationContext = legacyLocationContext(context.config.nlu);
    const prepared = await client.prepareTurn({
      turn_id: context.turnId,
      user_text: context.userText,
      ...(context.voiceProfileId ? { voice_profile_id: context.voiceProfileId } : {}),
      ...(context.config.businessAppId ? { app_id: context.config.businessAppId } : {}),
      ...(locationContext ? { location_context: locationContext } : {}),
      include: [
        "configs",
        "role",
        "voice_profile",
        "location",
        "wakeup_word",
      ],
    }, requestContext(context, "prepare"), context.cancellation);
    assertSupportedContextVersion(prepared.context_version);
    if (prepared.turn_id !== context.turnId) {
      throw new AgentError("AGENT_RESPONSE_INVALID", "Prepared turn ID mismatch", {
        phase: "transport",
      });
    }
    if (prepared.identity.product_id !== context.productId || prepared.identity.device_id !== context.deviceId) {
      throw new AgentError("AGENT_IDENTITY_MISMATCH", "Prepared identity does not match the active device", {
        phase: "transport",
      });
    }
    return prepared;
  }
}

type LegacyLocationContext = {
  city?: string;
  location?: string;
  client_ip?: string;
};

export function legacyLocationContext(
  nlu: Record<string, unknown>,
): LegacyLocationContext | undefined {
  const nested = isRecordValue(nlu.input) ? nlu.input : {};
  const context: LegacyLocationContext = {};
  const city = firstLocationString([nlu.city, nested.city], 256);
  const location = firstLocationString([nlu.location, nested.location], 256);
  const clientIp = firstLocationString([nlu.client_ip, nested.client_ip], 128);
  if (city) context.city = city;
  if (location) context.location = location;
  if (clientIp) context.client_ip = clientIp;
  return Object.keys(context).length > 0 ? context : undefined;
}

function firstLocationString(values: unknown[], maxLength: number): string | undefined {
  for (const value of values) {
    if (typeof value !== "string") continue;
    const normalized = value.trim();
    if (normalized) return normalized.slice(0, maxLength);
  }
  return undefined;
}

function isRecordValue(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

export function assertSupportedContextVersion(version: string): void {
  const match = /^(0|[1-9]\d*)(?:\.(?:0|[1-9]\d*))*$/.exec(version);
  const supportedMajor = AGENT_RUNTIME_CONTRACT_VERSION.split(".", 1)[0];
  if (!match || match[1] !== supportedMajor) {
    throw new AgentError(
      "AGENT_PROTOCOL_VERSION_UNSUPPORTED",
      "Agent Runtime context version is not supported",
      { phase: "transport" },
    );
  }
}

export function runtimeClient(context: VoiceTurnContext): AgentRuntimeClient {
  return new AgentRuntimeClient({
    baseUrl: context.config.baseUrl,
    tokenSecretKey: context.config.platformTokenSecretKey,
  });
}
