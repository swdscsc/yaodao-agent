import type { AiuiResolveResponse, MusicPlaylistItem } from "@listenai/agent-sdk";

export interface InterpretedAiuiDecision {
  handled: boolean;
  outcomeReason?: string;
  answer?: string;
  service?: string;
  playlist: MusicPlaylistItem[];
  frames: Array<Record<string, unknown>>;
}

const MAX_DEVICE_FRAME_BYTES = 16 << 10;
const MAX_AIUI_STRING_BYTES = 4 << 10;

/** Converts the Runtime's normalized AIUI result into Host device frames. */
export function interpretAiuiResponse(
  rawResponse: unknown,
  userText: string,
  turnId: string,
): InterpretedAiuiDecision {
  if (!isRecord(rawResponse)) return { handled: false, playlist: [], frames: [] };
  const response = rawResponse as Partial<AiuiResolveResponse>;
  const handled = response.handled === true
    || (response.handled === undefined && response.accepted === true && response.outcome === "direct_return");
  const outcomeReason = typeof response.outcome_reason === "string" ? response.outcome_reason : undefined;
  if (!handled) {
    return {
      handled: false,
      ...(outcomeReason ? { outcomeReason } : {}),
      playlist: [],
      frames: [],
    };
  }
  const service = typeof response.service === "string" ? response.service.trim() : "";
  const answer = typeof response.answer_text === "string" ? response.answer_text : "";
  const data = Array.isArray(response.data) ? response.data : [];
  return {
    handled: true,
    outcomeReason,
    ...(answer ? { answer } : {}),
    ...(service ? { service } : {}),
    playlist: Array.isArray(response.playlist) ? response.playlist : [],
    frames: service ? buildAiuiFrames(service, userText, turnId, {
      service,
      ...(typeof response.intent === "string" ? { intent: response.intent } : {}),
      ...(answer ? { answer_text: answer } : {}),
      ...(data.length > 0 ? { data } : {}),
    }) : [],
  };
}

export function normalizeAiuiServices(value: unknown): string[] | undefined {
  if (!Array.isArray(value)) return undefined;
  const output: string[] = [];
  for (const item of value) {
    const direct = typeof item === "string" ? item.trim() : "";
    const source = isRecord(item) ? item : {};
    const nested = isRecord(source.aiui) ? source.aiui : {};
    const candidate = direct
      || (typeof nested.name === "string" ? nested.name.trim() : "")
      || (typeof source.service === "string" ? source.service.trim() : "");
    const service = candidate.replace(/^AIUI\./i, "");
    if (service && !output.includes(service)) output.push(service);
  }
  return output.length > 0 ? output : undefined;
}

function buildAiuiFrames(
  service: string,
  userText: string,
  turnId: string,
  result: Record<string, unknown>,
): Array<Record<string, unknown>> {
  const callId = `aiui:${turnId}`;
  const name = `aiui_${service}`.replace(/[^A-Za-z0-9_-]/g, "_").slice(0, 64);
  const base = { type: "CUSTOM", nlp_origin: "xiaoling_mcp" };
  const start = {
    ...base,
    payload: {
      method: "tools/start",
      id: callId,
      params: { name, arguments: { text: truncateUtf8(userText, MAX_AIUI_STRING_BYTES) } },
    },
  };
  const delta = {
    ...base,
    payload: {
      method: "tools/delta",
      id: callId,
      params: { name, result: fitResultToDeviceFrame(base, callId, name, result) },
    },
  };
  return [
    start,
    delta,
    { ...base, payload: { method: "tools/stop", id: callId, params: { name } } },
  ];
}

function fitResultToDeviceFrame(
  base: Record<string, unknown>,
  callId: string,
  name: string,
  result: Record<string, unknown>,
): Record<string, unknown> {
  const { data, ...fixed } = result;
  const bounded: Record<string, unknown> = { ...fixed };
  if (!Array.isArray(data)) return bounded;
  const accepted: unknown[] = [];
  for (const item of data) {
    const candidate = [...accepted, item];
    const frame = {
      ...base,
      payload: { method: "tools/delta", id: callId, params: { name, result: { ...bounded, data: candidate } } },
    };
    if (utf8ByteLength(JSON.stringify(frame)) > MAX_DEVICE_FRAME_BYTES) continue;
    accepted.push(item);
  }
  if (accepted.length > 0) bounded.data = accepted;
  return bounded;
}

function truncateUtf8(value: string, maxBytes: number): string {
  if (utf8ByteLength(value) <= maxBytes) return value;
  let output = "";
  let bytes = 0;
  for (const character of value) {
    const size = utf8ByteLength(character);
    if (bytes + size > maxBytes) break;
    output += character;
    bytes += size;
  }
  return output;
}

function utf8ByteLength(value: string): number {
  let bytes = 0;
  for (const character of value) {
    const codePoint = character.codePointAt(0) ?? 0;
    bytes += codePoint <= 0x7f ? 1 : codePoint <= 0x7ff ? 2 : codePoint <= 0xffff ? 3 : 4;
  }
  return bytes;
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}
