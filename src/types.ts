import type {
  AgentRuntimeMemoryPolicy,
  CancellationToken,
  PrepareTurnResponse,
} from "@listenai/agent-sdk";
import type { NormalizedSessionConfig } from "./config/schema";
import type { ServerDsaPolicy } from "./tools/toolPolicies";

export interface VoiceTurnContext {
  sessionId: string;
  turnId: string;
  requestId: string;
  deviceId: string;
  productId: string;
  userText: string;
  voiceProfileId?: string;
  vprInfo?: Record<string, unknown>;
  memoryPolicy: AgentRuntimeMemoryPolicy;
  dsaPolicy: ServerDsaPolicy;
  config: NormalizedSessionConfig;
  cancellation: CancellationToken;
}

export interface PreparedVoiceContext {
  prepared: PrepareTurnResponse;
  longMemory: string;
  preferences: Array<Record<string, unknown>>;
  knowledge: string;
  warnings: Array<{ section: string; code: string; message: string }>;
}

export function requestContext(
  context: VoiceTurnContext,
  suffix: string,
  toolCallId?: string,
): {
  sessionId: string;
  turnId: string;
  requestId: string;
  appId?: string;
  toolCallId?: string;
} {
  return {
    sessionId: context.sessionId,
    turnId: context.turnId,
    requestId: boundedCorrelation(`${context.requestId}:${suffix}`),
    ...(context.config.businessAppId ? { appId: context.config.businessAppId } : {}),
    ...(toolCallId ? { toolCallId } : {}),
  };
}

export function boundedCorrelation(value: string): string {
  const cleaned = value.replace(/[^A-Za-z0-9._:-]/g, "_");
  return cleaned.length <= 128 ? cleaned : cleaned.slice(cleaned.length - 128);
}

export function uuidV4(): string {
  const bytes: number[] = [];
  for (let index = 0; index < 16; index += 1) {
    bytes.push(Math.floor(Math.random() * 256));
  }
  bytes[6] = (bytes[6] & 0x0f) | 0x40;
  bytes[8] = (bytes[8] & 0x3f) | 0x80;
  const hex = bytes.map((value) => value.toString(16).padStart(2, "0"));
  return [
    hex.slice(0, 4).join(""),
    hex.slice(4, 6).join(""),
    hex.slice(6, 8).join(""),
    hex.slice(8, 10).join(""),
    hex.slice(10, 16).join(""),
  ].join("-");
}
