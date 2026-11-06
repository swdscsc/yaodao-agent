import type { FunctionTool } from "../model/types";
import type { CancellationToken } from "../runtime/cancellation";
import type { MusicPlayback, MusicPlaylistItem } from "../transport/agentRuntimeApi";
import { encodeUTF8 } from "../http/utf8";

export interface ToolCall {
  id: string;
  name: string;
  arguments: string;
  parsedArguments: Record<string, unknown>;
}

export interface ToolResult {
  callId: string;
  content: ToolContent[];
  isError: boolean;
  control: { agentStop: boolean };
  artifacts: ToolArtifact[];
}

export interface TextToolContent {
  type: "text";
  text: string;
}

type AtLeastOnePayload<T extends Record<string, unknown>> = {
  [Key in keyof T]: Required<Pick<T, Key>> & Partial<Omit<T, Key>>;
}[keyof T];

interface ImageToolContentBase {
  type: "image";
  kind: "camera" | "generated" | "edited" | "input" | "unknown";
  mime_type?: "image/png" | "image/jpeg" | "image/gif" | "image/webp";
  name?: string;
}

export type ImageToolContent = ImageToolContentBase & AtLeastOnePayload<{
  url: string;
  data: string;
}>;

interface AudioToolContentBase {
  type: "audio";
  mime_type?: "audio/mpeg" | "audio/wav" | "audio/ogg" | "audio/webm" | "audio/aac" | "audio/mp4" | "audio/flac";
  name?: string;
}

export type AudioToolContent = AudioToolContentBase & AtLeastOnePayload<{
  url: string;
  data: string;
}>;

interface ResourceToolContentBase {
  type: "resource";
  mime_type?: "application/json" | "application/pdf" | "application/octet-stream" | "text/plain" | "text/markdown" | "text/csv";
  name?: string;
}

export type ResourceToolContent = ResourceToolContentBase & AtLeastOnePayload<{
  uri: string;
  url: string;
  data: string;
  text: string;
}>;

export type ToolContent = TextToolContent | ImageToolContent | AudioToolContent | ResourceToolContent;

export interface MusicPlaylistArtifact {
  type: "music_playlist";
  playback: MusicPlayback;
  items: MusicPlaylistItem[];
}

export interface DeviceActionArtifact {
  type: "device_action";
  action: "netease_token_refresh" | "playback_exit";
}

export interface OpenClawDispatchArtifact {
  type: "openclaw_dispatch";
  status: "accepted";
  capability: "chat" | "memo" | "alarm" | "photo" | "image" | "realtime";
}

export type ToolArtifact =
  | ImageToolContent
  | AudioToolContent
  | ResourceToolContent
  | OpenClawDispatchArtifact
  | MusicPlaylistArtifact
  | DeviceActionArtifact;

export interface ToolExecutionContext {
  sessionId: string;
  turnId: string;
  requestId: string;
  appId?: string;
  userText?: string;
  cancellation: CancellationToken;
}

export type ToolExecutionOwner = Pick<ToolExecutionContext, "sessionId" | "turnId">;

export interface ToolExecutor {
  execute(call: ToolCall, context: ToolExecutionContext): Promise<ToolResult>;
  cancel?(callId: string, reason?: string, owner?: ToolExecutionOwner): void;
}

export interface RegisteredTool {
  definition: FunctionTool;
  executor: ToolExecutor;
}

export function toolResultText(result: ToolResult, maxBytes = 64 << 10): string {
  let output = "";
  for (const item of result.content) {
    if (item.type !== "text" || typeof item.text !== "string" || !item.text) continue;
    const separator = output ? "\n" : "";
    const remaining = maxBytes - encodeUTF8(output).length;
    if (remaining <= 0) break;
    output += truncateUTF8(separator + item.text, remaining);
  }
  return output;
}

export function modelToolResultText(result: ToolResult, maxBytes = 64 << 10): string {
  const images = legacyImageContent(result);
  return images.length > 0
    ? boundedLegacyImageResult(result, images, maxBytes)
    : toolResultText(result, maxBytes);
}

type LegacyImageContent = {
  type: "image";
  image?: string;
  data?: string;
};

function legacyImageContent(result: ToolResult): LegacyImageContent[] {
  const output: LegacyImageContent[] = [];
  const seen = new Set<string>();
  for (const item of [...result.content, ...result.artifacts]) {
    if (item.type !== "image") continue;
    const source = item.url || item.data;
    if (!source) continue;
    const identity = `${item.kind}\u0000${source}`;
    if (seen.has(identity)) continue;
    seen.add(identity);
    output.push({
      type: "image",
      ...(item.kind === "camera" ? { data: source } : { image: source }),
    });
  }
  return output;
}

function boundedLegacyImageResult(
  result: ToolResult,
  images: LegacyImageContent[],
  maxBytes: number,
): string {
  const serialize = (content: Array<TextToolContent | LegacyImageContent>): string => JSON.stringify({
    message: {
      ...(result.control.agentStop ? { agent_stop: true } : {}),
      content,
    },
  });
  const selectedImages: LegacyImageContent[] = [];
  for (const image of images) {
    const candidate = serialize([...selectedImages, image]);
    if (encodeUTF8(candidate).length > maxBytes) continue;
    selectedImages.push(image);
  }
  if (selectedImages.length === 0) return "";

  const textContent: TextToolContent[] = [];
  for (const item of result.content) {
    if (item.type !== "text" || !item.text) continue;
    const candidate = serialize([...textContent, item, ...selectedImages]);
    if (encodeUTF8(candidate).length <= maxBytes) {
      textContent.push(item);
      continue;
    }
    const text = truncateTextForLegacyEnvelope(
      item.text,
      (value) => encodeUTF8(serialize([
        ...textContent,
        { type: "text", text: value },
        ...selectedImages,
      ])).length <= maxBytes,
    );
    if (text) textContent.push({ type: "text", text });
    break;
  }
  return serialize([...textContent, ...selectedImages]);
}

function truncateTextForLegacyEnvelope(text: string, fits: (value: string) => boolean): string {
  const characters = Array.from(text);
  let low = 0;
  let high = characters.length;
  while (low < high) {
    const middle = Math.ceil((low + high) / 2);
    if (fits(characters.slice(0, middle).join(""))) low = middle;
    else high = middle - 1;
  }
  return characters.slice(0, low).join("");
}

const MUSIC_PLAYBACK = new Set<MusicPlayback>(["kuwo", "netease", "general", "audio_link", "tf_card"]);
const IMAGE_KINDS = new Set(["camera", "generated", "edited", "input", "unknown"]);
const IMAGE_MIME_TYPES = new Set(["image/png", "image/jpeg", "image/gif", "image/webp"]);
const AUDIO_MIME_TYPES = new Set(["audio/mpeg", "audio/wav", "audio/ogg", "audio/webm", "audio/aac", "audio/mp4", "audio/flac"]);
const RESOURCE_MIME_TYPES = new Set([
  "application/json", "application/pdf", "application/octet-stream",
  "text/plain", "text/markdown", "text/csv",
]);
const OPENCLAW_CAPABILITIES = new Set(["chat", "memo", "alarm", "photo", "image", "realtime"]);

export function normalizeClosedToolContent(value: unknown): ToolContent | null {
  if (!isRecord(value) || typeof value.type !== "string") return null;
  if (value.type === "text") {
    return hasOnlyKeys(value, ["type", "text"])
      && typeof value.text === "string"
      && encodeUTF8(value.text).length <= 524_288
      ? { type: "text", text: value.text }
      : null;
  }
  if (value.type === "image") {
    return normalizeImage(value);
  }
  if (value.type === "audio") {
    return normalizeAudio(value);
  }
  if (value.type === "resource") {
    return normalizeResource(value);
  }
  return null;
}

export function normalizeClosedToolArtifact(value: unknown): ToolArtifact | null {
  if (!isRecord(value) || typeof value.type !== "string") return null;
  if (value.type === "image" || value.type === "audio" || value.type === "resource") {
    return normalizeClosedToolContent(value) as Exclude<ToolArtifact, MusicPlaylistArtifact | DeviceActionArtifact | OpenClawDispatchArtifact> | null;
  }
  if (value.type === "openclaw_dispatch") {
    return hasOnlyKeys(value, ["type", "status", "capability"])
      && value.status === "accepted"
      && OPENCLAW_CAPABILITIES.has(String(value.capability))
      ? {
        type: "openclaw_dispatch",
        status: "accepted",
        capability: value.capability as OpenClawDispatchArtifact["capability"],
      }
      : null;
  }
  if (value.type === "music_playlist") {
    if (!hasOnlyKeys(value, ["type", "playback", "items"])
      || !MUSIC_PLAYBACK.has(value.playback as MusicPlayback)
      || !Array.isArray(value.items)
      || value.items.length < 1
      || value.items.length > 100) return null;
    const items: MusicPlaylistItem[] = [];
    for (const item of value.items) {
      const normalized = normalizeMusicPlaylistItem(item);
      if (!normalized) return null;
      items.push(normalized);
    }
    return {
      type: "music_playlist",
      playback: value.playback as MusicPlayback,
      items,
    };
  }
  if (value.type === "device_action"
    && hasOnlyKeys(value, ["type", "action"])
    && (value.action === "netease_token_refresh" || value.action === "playback_exit")) {
    return { type: "device_action", action: value.action };
  }
  return null;
}

export function normalizeClosedToolResult(
  value: unknown,
  callId: string,
  requireCallId = false,
): ToolResult | null {
  if (!isRecord(value)
    || !hasOnlyKeys(value, requireCallId
      ? ["callId", "content", "isError", "control", "artifacts"]
      : ["content", "isError", "control", "artifacts"])
    || (requireCallId && value.callId !== callId)
    || !Array.isArray(value.content)
    || typeof value.isError !== "boolean"
    || !isRecord(value.control)
    || !hasOnlyKeys(value.control, ["agentStop"])
    || typeof value.control.agentStop !== "boolean"
    || !Array.isArray(value.artifacts)) return null;
  const content: ToolContent[] = [];
  for (const item of value.content) {
    const normalized = normalizeClosedToolContent(item);
    if (!normalized) return null;
    content.push(normalized);
  }
  const artifacts: ToolArtifact[] = [];
  for (const item of value.artifacts) {
    const normalized = normalizeClosedToolArtifact(item);
    if (!normalized) return null;
    artifacts.push(normalized);
  }
  return {
    callId,
    content,
    isError: value.isError,
    control: { agentStop: value.control.agentStop },
    artifacts,
  };
}

function normalizeImage(value: Record<string, unknown>): ImageToolContent | null {
  if (!hasOnlyKeys(value, ["type", "kind", "url", "data", "mime_type", "name"])
    || !IMAGE_KINDS.has(String(value.kind))) return null;
  const media = normalizeMediaFields(value, IMAGE_MIME_TYPES, "image");
  if (!media) return null;
  return {
    type: "image",
    kind: value.kind as ImageToolContent["kind"],
    ...(media.url ? { url: media.url } : {}),
    ...(media.data ? { data: media.data } : {}),
    ...(media.mime_type ? { mime_type: media.mime_type as ImageToolContent["mime_type"] } : {}),
    ...(media.name ? { name: media.name } : {}),
  } as ImageToolContent;
}

function normalizeAudio(value: Record<string, unknown>): AudioToolContent | null {
  if (!hasOnlyKeys(value, ["type", "url", "data", "mime_type", "name"])) return null;
  const media = normalizeMediaFields(value, AUDIO_MIME_TYPES, "audio");
  return media ? {
    type: "audio",
    ...(media.url ? { url: media.url } : {}),
    ...(media.data ? { data: media.data } : {}),
    ...(media.mime_type ? { mime_type: media.mime_type as AudioToolContent["mime_type"] } : {}),
    ...(media.name ? { name: media.name } : {}),
  } as AudioToolContent : null;
}

function normalizeResource(value: Record<string, unknown>): ResourceToolContent | null {
  if (!hasOnlyKeys(value, ["type", "uri", "url", "data", "text", "mime_type", "name"])) return null;
  const uri = value.uri === undefined ? undefined : safePublicHTTPSURL(value.uri);
  const url = value.url === undefined ? undefined : safePublicHTTPSURL(value.url);
  const data = value.data === undefined ? undefined : normalizeDataURI(value.data, RESOURCE_MIME_TYPES, "");
  const mimeType = optionalEnum(value.mime_type, RESOURCE_MIME_TYPES);
  const name = optionalBoundedString(value.name, 512);
  const text = value.text === undefined
    ? undefined
    : typeof value.text === "string" && encodeUTF8(value.text).length <= 524_288
      ? value.text
      : null;
  if (uri === null || url === null || data === null || mimeType === null || name === null || text === null
    || (!uri && !url && !data && text === undefined)
    || (data && mimeType && data.mimeType !== mimeType)) return null;
  return {
    type: "resource",
    ...(uri ? { uri } : {}),
    ...(url ? { url } : {}),
    ...(data ? { data: data.value } : {}),
    ...(text !== undefined ? { text } : {}),
    ...(mimeType ? { mime_type: mimeType as ResourceToolContent["mime_type"] } : {}),
    ...(name ? { name } : {}),
  } as ResourceToolContent;
}

function normalizeMediaFields(
  value: Record<string, unknown>,
  allowedMimeTypes: Set<string>,
  dataKind: "image" | "audio",
): { url?: string; data?: string; mime_type?: string; name?: string } | null {
  const url = value.url === undefined ? undefined : safePublicHTTPSURL(value.url);
  const data = value.data === undefined ? undefined : normalizeDataURI(value.data, allowedMimeTypes, dataKind);
  const mimeType = optionalEnum(value.mime_type, allowedMimeTypes);
  const name = optionalBoundedString(value.name, 512);
  if (url === null || data === null || mimeType === null || name === null || (!url && !data)
    || (data && mimeType && data.mimeType !== mimeType)) return null;
  return {
    ...(url ? { url } : {}),
    ...(data ? { data: data.value } : {}),
    ...(mimeType ? { mime_type: mimeType } : {}),
    ...(name ? { name } : {}),
  };
}

function normalizeDataURI(
  value: unknown,
  allowedMimeTypes: Set<string>,
  expectedKind: "" | "image" | "audio",
): { value: string; mimeType: string } | null {
  if (typeof value !== "string" || value.length > 524_288) return null;
  const match = /^data:([^;,]+);base64,([A-Za-z0-9+/]+={0,2})$/.exec(value);
  if (!match || !allowedMimeTypes.has(match[1]) || (expectedKind && !match[1].startsWith(`${expectedKind}/`))) return null;
  const payload = match[2];
  if (payload.length % 4 !== 0 || /=[^=]/.test(payload) || /={3,}$/.test(payload) || !hasCanonicalPaddingBits(payload)) {
    return null;
  }
  return { value, mimeType: match[1] };
}

function hasCanonicalPaddingBits(payload: string): boolean {
  const padding = payload.endsWith("==") ? 2 : payload.endsWith("=") ? 1 : 0;
  if (padding === 0) return true;
  const character = payload[payload.length - padding - 1];
  const index = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/".indexOf(character);
  if (index < 0) return false;
  return padding === 2 ? (index & 0x0f) === 0 : (index & 0x03) === 0;
}

function normalizeMusicPlaylistItem(value: unknown): MusicPlaylistItem | null {
  if (!isRecord(value)
    || !hasOnlyKeys(value, [
      "item_id", "name", "playable", "url", "source", "duration", "artists", "album",
      "cover_url", "file_name", "file_path",
    ])
    || !boundedString(value.item_id, 256)
    || !boundedString(value.name, 512)
    || (value.playable !== 0 && value.playable !== 1)) return null;
  const optionalStrings = {
    source: boundedOptionalString(value.source, 128),
    file_name: boundedOptionalString(value.file_name, 512),
    file_path: boundedOptionalString(value.file_path, 2_048),
  };
  if (Object.values(optionalStrings).some((item) => item === null)) return null;
  if (optionalStrings.file_path && (!optionalStrings.file_path.startsWith("/") || optionalStrings.file_path.length < 2)) return null;
  const url = value.url === undefined ? undefined : safePublicHTTPSURL(value.url);
  const coverURL = value.cover_url === undefined ? undefined : safePublicHTTPSURL(value.cover_url);
  if (url === null || coverURL === null) return null;
  if (value.duration !== undefined
    && (typeof value.duration !== "number"
      || !Number.isInteger(value.duration)
      || value.duration < 0
      || value.duration > 86_400_000)) return null;
  const artists = value.artists === undefined ? undefined : normalizeMusicIdentities(value.artists);
  const album = value.album === undefined ? undefined : normalizeMusicIdentity(value.album);
  if (artists === null || album === null) return null;
  return {
    item_id: value.item_id as string,
    name: value.name as string,
    playable: value.playable,
    ...(url ? { url } : {}),
    ...(optionalStrings.source ? { source: optionalStrings.source } : {}),
    ...(value.duration !== undefined ? { duration: value.duration } : {}),
    ...(artists ? { artists } : {}),
    ...(album ? { album } : {}),
    ...(coverURL ? { cover_url: coverURL } : {}),
    ...(optionalStrings.file_name ? { file_name: optionalStrings.file_name } : {}),
    ...(optionalStrings.file_path ? { file_path: optionalStrings.file_path } : {}),
  };
}

function normalizeMusicIdentities(value: unknown): Array<{ id: string; name: string }> | null {
  if (!Array.isArray(value) || value.length > 32) return null;
  const output: Array<{ id: string; name: string }> = [];
  for (const item of value) {
    const normalized = normalizeMusicIdentity(item);
    if (!normalized) return null;
    output.push(normalized);
  }
  return output;
}

function normalizeMusicIdentity(value: unknown): { id: string; name: string } | null {
  if (!isRecord(value)
    || !hasOnlyKeys(value, ["id", "name"])
    || !boundedString(value.id, 256)
    || !boundedString(value.name, 512)) return null;
  return { id: value.id as string, name: value.name as string };
}

function safePublicHTTPSURL(value: unknown): string | null {
  if (typeof value !== "string" || value.length === 0 || value.length > 8_192 || /[\u0000-\u0020\u007f\\]/.test(value)) {
    return null;
  }
  const match = /^https:\/\/([^/?#]+)(?:\/[^?#]*)?(?:\?[^#]*)?$/i.exec(value);
  if (!match || match[1].includes("@") || match[1].includes("%")) return null;
  const authority = match[1];
  if (authority.startsWith("[")) return null;
  const parts = authority.split(":");
  if (parts.length > 2 || (parts.length === 2 && !validPort(parts[1]))) return null;
  const hostname = parts[0].toLowerCase();
  if (!isPublicURLHostname(hostname)) return null;
  return value;
}

// Fetchers must still enforce resolved-address policy to contain DNS rebinding.
function isPublicURLHostname(hostname: string): boolean {
  const ipv4 = canonicalIPv4(hostname);
  if (ipv4) return !isSpecialPurposeIPv4(ipv4);
  if (looksLikeIPv4(hostname)) return false;
  if (hostname.length > 253 || !hostname.includes(".")) return false;
  const labels = hostname.split(".");
  if (labels.some((label) => (
    label.length === 0
    || label.length > 63
    || !/^[a-z0-9](?:[a-z0-9-]*[a-z0-9])?$/.test(label)
  ))) return false;
  return !hasPrivateSuffix(hostname);
}

function canonicalIPv4(hostname: string): number[] | null {
  if (!/^(?:0|[1-9]\d{0,2})(?:\.(?:0|[1-9]\d{0,2})){3}$/.test(hostname)) return null;
  const octets = hostname.split(".").map(Number);
  return octets.every((value) => value <= 255) ? octets : null;
}

function looksLikeIPv4(hostname: string): boolean {
  return /^(?:0x[0-9a-f]+|\d+)(?:\.(?:0x[0-9a-f]+|\d+)){0,3}$/i.test(hostname);
}

function hasPrivateSuffix(hostname: string): boolean {
  return [
    "localhost",
    "local",
    "localdomain",
    "internal",
    "intranet",
    "lan",
    "home",
    "home.arpa",
    "corp",
    "private",
  ].some((suffix) => hostname === suffix || hostname.endsWith(`.${suffix}`));
}

function isSpecialPurposeIPv4(octets: number[]): boolean {
  const address = ipv4Number(octets);
  return inIPv4Block(address, 0x00000000, 8)
    || inIPv4Block(address, 0x0a000000, 8)
    || inIPv4Block(address, 0x64400000, 10)
    || inIPv4Block(address, 0x7f000000, 8)
    || inIPv4Block(address, 0xa9fe0000, 16)
    || inIPv4Block(address, 0xac100000, 12)
    || inIPv4Block(address, 0xc0000000, 24)
    || inIPv4Block(address, 0xc0000200, 24)
    || inIPv4Block(address, 0xc01fc400, 24)
    || inIPv4Block(address, 0xc034c100, 24)
    || inIPv4Block(address, 0xc0586300, 24)
    || inIPv4Block(address, 0xc0a80000, 16)
    || inIPv4Block(address, 0xc0af3000, 24)
    || inIPv4Block(address, 0xc6120000, 15)
    || inIPv4Block(address, 0xc6336400, 24)
    || inIPv4Block(address, 0xcb007100, 24)
    || inIPv4Block(address, 0xe0000000, 4)
    || inIPv4Block(address, 0xf0000000, 4);
}

function ipv4Number(octets: number[]): number {
  return ((octets[0] << 24) | (octets[1] << 16) | (octets[2] << 8) | octets[3]) >>> 0;
}

function inIPv4Block(address: number, network: number, prefixLength: number): boolean {
  const mask = prefixLength === 0 ? 0 : (0xffffffff << (32 - prefixLength)) >>> 0;
  return (address & mask) === (network & mask);
}

function validPort(value: string): boolean {
  if (!/^\d{1,5}$/.test(value)) return false;
  const port = Number(value);
  return port >= 1 && port <= 65_535;
}

function optionalEnum(value: unknown, allowed: Set<string>): string | undefined | null {
  if (value === undefined) return undefined;
  return typeof value === "string" && allowed.has(value) ? value : null;
}

function optionalBoundedString(value: unknown, maximum: number): string | undefined | null {
  if (value === undefined) return undefined;
  return boundedString(value, maximum) ? value as string : null;
}

function boundedOptionalString(value: unknown, maximum: number): string | undefined | null {
  if (value === undefined) return undefined;
  return boundedString(value, maximum) ? value as string : null;
}

function boundedString(value: unknown, maximum: number): boolean {
  return typeof value === "string"
    && value.length > 0
    && encodeUTF8(value).length <= maximum
    && !/[\u0000-\u001f\u007f]/.test(value);
}

function hasOnlyKeys(value: Record<string, unknown>, allowed: string[]): boolean {
  const names = new Set(allowed);
  return Object.keys(value).every((key) => names.has(key));
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function truncateUTF8(value: string, maximumBytes: number): string {
  if (encodeUTF8(value).length <= maximumBytes) return value;
  let output = "";
  let bytes = 0;
  for (const character of value) {
    const size = encodeUTF8(character).length;
    if (bytes + size > maximumBytes) break;
    output += character;
    bytes += size;
  }
  return output;
}
