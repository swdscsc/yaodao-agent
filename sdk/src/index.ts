export * from "./host";

export { AgentError, asAgentError } from "./runtime/errors";
export type { AgentErrorOptions, AgentErrorPhase } from "./runtime/errors";
export {
  AgentCancelledError,
  CancellationTokenSource,
  uncancelledToken,
} from "./runtime/cancellation";
export type { CancellationToken } from "./runtime/cancellation";
export type {
  AgentEvent,
  AgentEventHandlers,
  OutputMeta,
  RunResult,
} from "./runtime/events";

export { OpenAICompatibleSSEDecoder } from "./model/sseDecoder";
export type { OpenAIStreamEvent, SSEDecoderOptions } from "./model/sseDecoder";
export { HTTPJSONClient } from "./http/jsonClient";
export type { HTTPJSONHeaders, HTTPJSONRequest } from "./http/jsonClient";
export { OpenAICompatibleChatModel } from "./model/openaiCompatible";
export type { OpenAICompatibleChatModelOptions } from "./model/openaiCompatible";
export { KVBackedCircuitBreaker, customModelCircuitKey } from "./model/circuitBreaker";
export type { KVBackedCircuitBreakerOptions, ModelCircuitBreaker } from "./model/circuitBreaker";
export { PlatformChatModel, toWireMessage } from "./model/platform";
export type { PlatformChatModelOptions } from "./model/platform";
export type {
  AssistantToolCall,
  ChatMessage as AgentChatMessage,
  ChatMessageContent as AgentChatMessageContent,
  ChatModel,
  ContentPart,
  FunctionTool,
  ModelRequest,
  ModelRunContext,
  ModelRunHandle,
  ModelRunResult,
  ModelStreamHandlers,
  ModelUsage,
  ToolCallDelta,
  ToolChoice,
} from "./model/types";

export { DefaultReActEngine } from "./react/reactEngine";
export type {
  ModelFallbackCandidate,
  ModelFallbackPolicy,
  ReActEngine,
  ReActInput,
} from "./react/reactEngine";

export { ToolRegistry, validateFunctionToolDefinition } from "./tools/registry";
export type { ToolRegistryOptions } from "./tools/registry";
export { DuplicateToolCallGuard, toolCallSignature } from "./tools/duplicateGuard";
export {
  CustomHTTPToolExecutor,
  LocalToolExecutor,
  PlatformToolExecutor,
} from "./tools/executors";
export type {
  CustomHTTPToolExecutorOptions,
  LocalToolExecutorOptions,
  LocalToolHandler,
  PlatformToolExecutorOptions,
} from "./tools/executors";
export {
  DeviceToolRouter,
  MAX_DEVICE_TOOL_CALL_FRAME_BYTES,
} from "./tools/deviceExecutor";
export type {
  DeviceToolBinding,
  DeviceToolResolution,
  DeviceToolRouterOptions,
} from "./tools/deviceExecutor";
export {
  normalizeClosedToolArtifact,
  normalizeClosedToolContent,
  normalizeClosedToolResult,
  toolResultText,
} from "./tools/types";
export type {
  AudioToolContent,
  ToolArtifact as AgentToolArtifact,
  ToolCall as AgentToolCall,
  ToolContent as AgentToolContent,
  DeviceActionArtifact,
  ImageToolContent,
  OpenClawDispatchArtifact,
  ResourceToolContent,
  TextToolContent,
  ToolExecutionContext,
  ToolExecutionOwner,
  ToolExecutor,
  MusicPlaylistArtifact,
  ToolResult as AgentToolResult,
} from "./tools/types";

export { MCPClient } from "./mcp/client";
export { normalizeMCPToolResult } from "./mcp/client";
export type {
  JSONRPCRequest,
  MCPClientOptions,
  MCPToolDefinition,
  MCPTransport,
} from "./mcp/client";
export { HostMCPHTTPTransport } from "./mcp/httpTransport";
export type { HostMCPHTTPTransportOptions } from "./mcp/httpTransport";
export { MCPToolProvider, safeMCPToolAlias } from "./mcp/provider";
export type { MCPClientLike, McpServerConfig } from "./mcp/provider";

export { AgentRuntimeTransport } from "./transport/agentRuntime";
export type {
  AgentRuntimeRequestContext,
  AgentRuntimeStreamRequest,
  AgentRuntimeTransportOptions,
  HTTPRunHandle,
} from "./transport/agentRuntime";
export { AgentRuntimeClient } from "./transport/agentRuntimeApi";
export type {
  AgentConfigLayer,
  AgentRuntimeMemoryPolicy,
  AgentRuntimeDsaPolicy,
  AgentRuntimePolicy,
  AgentWarning,
  AiuiOutcomeReason,
  AiuiResolveRequest,
  AiuiResolveResponse,
  AiuiSlot,
  AiuiWebhookOutcome,
  CompleteTurnResponse,
  CompleteTurnRequest,
  InteractionRecord,
  DeviceCapability,
  DeviceActionRequest,
  AgentFeature,
  KnowledgeQueryRequest as AgentKnowledgeQueryRequest,
  KnowledgeQueryResponse as AgentKnowledgeQueryResponse,
  KnowledgeSource,
  MemoryRecallRequest,
  MemoryRecallResponse,
  MemoryStoreRequest,
  MusicPlayback,
  MusicPlaylistItem,
  PreferenceRecord,
  PreferenceUpdateRequest,
  PrepareTurnRequest,
  PrepareTurnInclude,
  PrepareTurnResponse,
  ResolvedToolBinding,
  RoleContext,
  ToolBinding as AgentToolBinding,
  ToolCatalogResponse,
  ToolResolveClientTool,
  ToolResolveRequest,
  ToolResolveResponse,
  TrustedIdentity,
  UpgradeActionResponse,
  VoiceProfileContext,
  VoiceProfileHobbyRequest,
  VoiceProfileHobbyEvent,
  WriteResponse,
} from "./transport/agentRuntimeApi";

export const AGENT_RUNTIME_CONTRACT_VERSION = "1.0.0";

import type { ChatRequest, ChatChunk, TTSRequest, TTSOpenRequest, TextStreamOpenRequest, KnowledgeQueryRequest, KnowledgeQueryResponse, XiaolingAgentRequest, XiaolingAgentChunk, AIUISkillRequest, AIUISkillResult, EmitPayload, ListenAIHost, LogFields, LLMStreamEvents } from "./host";

// Helper: consume an LLM stream synchronously, yielding chunks.
// Uses host.sleep between empty polls.
export function* llmStream(req: ChatRequest): Generator<ChatChunk> {
  const id = host.llmChat(req);
  while (true) {
    const c = host.llmPoll(id);
    if (c === null) { host.sleep(20); continue; }
    yield c;
    if (c.done) return;
  }
}

// Helper: consume an LLM stream through short event callbacks. The Go runtime
// polls the stream outside the Goja worker and re-enters JS only for callbacks.
export function llmStreamEvents(req: ChatRequest, handlers: LLMStreamEvents): string {
  return host.llmStart(req, handlers);
}

// Helper: event-driven LLM stream with a Promise-friendly API. It keeps chunk
// handling event-driven, then resolves to the accumulated assistant text.
export function llmStreamAwait(req: ChatRequest, handlers: LLMStreamEvents = {}): Promise<string> {
  let answer = "";
  return new Promise((resolve, reject) => {
    llmStreamEvents(req, {
      onChunk: (chunk) => {
        if (chunk.delta) answer += chunk.delta;
        handlers.onChunk?.(chunk);
      },
      onDone: () => {
        handlers.onDone?.();
        resolve(answer);
      },
      onError: (error) => {
        try {
          handlers.onError?.(error);
        } finally {
          reject(error);
        }
      },
    });
  });
}

// AudioChunk is one frame from a TTS stream.
// codec = "pcm16le-16k"  → audio contains raw PCM bytes
// codec = "listenai-tts-url" → audio contains the TTS URL as UTF-8 bytes
export interface AudioChunk {
  audio: Uint8Array;
  codec: string;
}

// Helper: consume a TTS stream synchronously, yielding AudioChunk values.
// Uses host.sleep between empty polls.
export function* ttsStream(req: TTSRequest): Generator<AudioChunk> {
  const id = host.ttsSynthesize(req);
  while (true) {
    const c = host.ttsPoll(id);
    if (c === null) { host.sleep(20); continue; }
    if (c.audio && c.audio.length > 0) {
      yield { audio: c.audio, codec: c.codec };
    }
    if (c.done) return;
  }
}

export interface TTSStream {
  id: string;
  url: string;
  send(text: string): void;
  close(): void;
}

export function openTTSStream(req: TTSOpenRequest = {}): TTSStream {
  const opened = host.ttsOpen(req);
  let closed = false;
  return {
    id: opened.id,
    url: opened.url,
    send(text: string): void {
      if (closed || !text) return;
      host.ttsSend(opened.id, text);
    },
    close(): void {
      if (closed) return;
      closed = true;
      host.ttsClose(opened.id);
    },
  };
}

export function ensureTTSStream(req: TTSOpenRequest = {}): TTSStream {
  return openTTSStream(req);
}

export function closeActiveTTSStream(): void {
  host.ttsCloseActive();
}

export interface TextStream {
  id: string;
  url: string;
  send(text: string): void;
  close(): void;
}

export function openTextStream(req: TextStreamOpenRequest = {}): TextStream {
  const opened = host.textStreamOpen(req);
  let closed = false;
  return {
    id: opened.id,
    url: opened.url,
    send(text: string): void {
      if (closed || !text) return;
      host.textStreamSend(opened.id, text);
    },
    close(): void {
      if (closed) return;
      closed = true;
      host.textStreamClose(opened.id);
    },
  };
}

export function ensureTextStream(req: TextStreamOpenRequest = {}): TextStream {
  return openTextStream(req);
}

export function closeActiveTextStream(): void {
  host.textStreamCloseActive();
}

let currentLogFields: LogFields = {};

function withLogFields<T>(fields: LogFields, fn: () => T): T {
  const prev = currentLogFields;
  currentLogFields = fields;
  try {
    return fn();
  } finally {
    currentLogFields = prev;
  }
}

function writeLog(level: "debug" | "info" | "warn" | "error", message: string, fields: LogFields = {}): void {
  host.log(level, message, { origin: "agent", ...fields, ...currentLogFields });
}

export const log = {
  debug(message: string, fields?: LogFields): void { writeLog("debug", message, fields); },
  info(message: string, fields?: LogFields): void { writeLog("info", message, fields); },
  warn(message: string, fields?: LogFields): void { writeLog("warn", message, fields); },
  error(message: string, fields?: LogFields): void { writeLog("error", message, fields); },
};

// Helper: emit text shorthand.
export function emitText(sessionId: string, text: string): void {
  host.emit(sessionId, { tag: "text", val: text });
}

// Helper: emit a raw JSON frame passed through verbatim to the device's /nlp
// WebSocket (no wrapping/conversion). Objects are JSON.stringify-ed; string
// input must already be valid JSON, otherwise emit throws.
export function emitRaw(sessionId: string, frame: object | string): void {
  const val = typeof frame === "string" ? frame : JSON.stringify(frame);
  host.emit(sessionId, { tag: "raw", val });
}

export function knowledgeQuery(req: KnowledgeQueryRequest): KnowledgeQueryResponse {
  const raw = host.knowledgeQuery(req);
  return JSON.parse(raw) as KnowledgeQueryResponse;
}

export function* xiaolingAgentStream(req: XiaolingAgentRequest): Generator<XiaolingAgentChunk> {
  const id = host.xiaolingAgentChat(req);
  while (true) {
    const c = host.xiaolingAgentPoll(id);
    if (c === null) { host.sleep(20); continue; }
    yield c;
    if (c.done) return;
  }
}

export function aiuiSkill(req: AIUISkillRequest): AIUISkillResult {
  return host.aiuiSkill(req);
}

function bytesToString(bytes: Uint8Array): string {
  let out = "";
  for (let i = 0; i < bytes.length; i++) {
    out += String.fromCharCode(bytes[i]);
  }
  return out;
}

// Helper: emit a ListenAI TTS URL so the device can fetch and play audio.
// Wraps the URL in an action frame; the /nlp host handler converts it to the
// device's expected {"type":"TTS","url":"<url>"} message.
export function emitTTSStreamUrl(sessionId: string, url: string | Uint8Array): void {
  const data = typeof url === "string" ? url : bytesToString(url);
  host.emit(sessionId, { tag: "action", val: { kind: "tts-url", data } });
}

export function emitTextStreamUrl(sessionId: string, url: string | Uint8Array): void {
  const data = typeof url === "string" ? url : bytesToString(url);
  host.emit(sessionId, { tag: "action", val: { kind: "text-stream-url", data } });
}

// Emit only the NLP FINISH frame for the current turn. This does not close
// active TTS/text streams; close them explicitly after all text has been sent.
export function emitNLPFinish(sessionId: string): void {
  host.emit(sessionId, { tag: "action", val: { kind: "nlp-finish", data: "" } });
}

// IMPORTANT: Module-level variables and globalThis properties are shared across
// ALL sessions that run on the same Goja instance. Do NOT use module-level
// variables for per-session state — use host.kvGet/host.kvSet instead.
// Example of UNSAFE pattern:
//   var userPrefs = {};               // shared across sessions!
//   userPrefs[info.sessionId] = ...   // leaks to other sessions
// Example of SAFE pattern:
//   host.kvSet(info.sessionId + ".pref", value)  // session-scoped
type MaybePromise<T> = T | Promise<T>;

export interface Agent {
  onConnect?: (info: import("./host").SessionInfo) => MaybePromise<void>;
  onMessage: (msg: import("./host").DeviceMessage) => MaybePromise<void>;
  onInterrupt?: (sessionId: string) => MaybePromise<void>;
  onDisconnect?: (sessionId: string) => MaybePromise<void>;
}

// register: turn an Agent object into globalThis.guest with default no-op callbacks.
export function register(agent: Agent): void {
  (globalThis as any).guest = {
    onConnect: (info: import("./host").SessionInfo) => withLogFields({
      callback: "onConnect",
      sid: info.sessionId,
      deviceId: info.deviceId,
      productId: info.productId,
    }, () => (agent.onConnect ?? (() => null))(info)),
    onMessage: (msg: import("./host").DeviceMessage) => withLogFields({
      callback: "onMessage",
      sid: msg.sessionId,
      deviceId: msg.deviceId,
      productId: msg.productId,
      isLast: msg.isLast,
    }, () => agent.onMessage(msg)),
    onInterrupt: (sessionId: string) => withLogFields({
      callback: "onInterrupt",
      sid: sessionId,
    }, () => (agent.onInterrupt ?? (() => null))(sessionId)),
    onDisconnect: (sessionId: string) => withLogFields({
      callback: "onDisconnect",
      sid: sessionId,
    }, () => (agent.onDisconnect ?? (() => null))(sessionId)),
  };
}
