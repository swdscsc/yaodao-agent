// listenai:agent host bindings injected by the
// Goja runtime as globalThis.host. Types mirror the WIT v1.1 contract.

export interface SessionInfo {
  sessionId: string;
  deviceId: string;
  productId: string;
  connectedAt: string;
  isReconnect: boolean;
  reconnectCount: number;
}

export type MessageContent =
  | { tag: "text"; val: string }
  | { tag: "audio"; val: AudioFrame }
  | { tag: "event"; val: { kind: string; data: string } };

export interface AudioFrame { codec: string; data: Uint8Array; seq?: number; }

export interface DeviceMessage {
  sessionId: string;
  deviceId: string;
  productId: string;
  content: MessageContent;
  isLast: boolean;
  params: Array<[string, string]>;
  timestampMs: number;
}

export type ChatMessageContent = string | Array<Record<string, unknown>> | null;
export type ChatMessageToolCall = ToolCall | {
  id: string;
  type: "function";
  function: { name: string; arguments: string };
};
export interface ChatMessage {
  role: string;
  content: ChatMessageContent;
  toolCallId: string | null;
  toolCalls?: ChatMessageToolCall[] | null;
  meta?: Record<string, unknown> | null;
}

export interface ChatRequest {
  messages: ChatMessage[];
  provider?: string | null;
  model?: string | null;
  temperature?: number | null;
  maxTokens?: number | null;
  tools?: ToolDef[] | null;
  streaming: boolean;
  providerExtra?: string | null;
}

export interface ChatChunk {
  delta: string;
  done: boolean;
  toolCalls?: ToolCall[] | null;
  emotion?: string | null;
  metadata?: string | null;
}

export interface ToolDef { name: string; description: string; parametersSchema: string; endpoint?: string | null; }
export interface ToolCall { id: string; name: string; arguments: string; endpoint?: string | null; }
export interface ToolResult { callId: string; content: string; isError: boolean; }

export interface TTSRequest {
  text: string;
  provider?: string | null;
  voice?: string | null;
  speed?: number | null;
  volume?: number | null;
  emotion?: string | null;
  sampleRate?: number | null;
}

export interface TTSOpenRequest {
  provider?: string | null;
  voice?: string | null;
  speed?: number | null;
  volume?: number | null;
  emotion?: string | null;
  sampleRate?: number | null;
}

export interface TTSOpenResult {
  id: string;
  url: string;
}

export interface TextStreamOpenRequest {
  provider?: string | null;
}

export interface TextStreamOpenResult {
  id: string;
  url: string;
}

export interface KnowledgeQueryRequest {
  provider?: string | null;
  indexId: string;
  content: string;
  limit?: number | null;
  threshold?: number | null;
  isQueryReference?: boolean | null;
}

export type KnowledgeQueryResponse = Record<string, unknown> & { data?: unknown[] };

export interface XiaolingAgentRequest {
  provider?: string | null;
  user?: string | null;
  messages: ChatMessage[];
  tools?: unknown[] | null;
  persona?: string | null;
  nluProperty?: Record<string, unknown> | null;
  knowledges?: unknown[] | null;
  appid?: string | null;
  agentVersion?: string | null;
  agentVersionPolicy?: string | null;
  modelVersion?: string | null;
  toolProtocolVersion?: string | null;
  // When set, switches to the image-understanding (ls-interaction-img2txt)
  // model: a single multimodal user message (lastUserText + this image URL).
  image?: string | null;
}

export interface XiaolingAgentChunk {
  delta: string;
  answer: string;
  done: boolean;
  chatId?: string;
  isStoreChat: boolean;
  isAction: boolean;
  assistantMeta?: string;
  stop?: string | null;
  stopResp?: string;
  emo?: string | null;
  meta?: string;
  modelVersion?: string;
  sourceData?: string;
}

export interface AIUISkillRequest {
  provider?: string | null;
  text: string;
  uid?: string | null;
  appid?: string | null;
  appkey?: string | null;
  scene?: string | null;
  lat?: string | null;
  lng?: string | null;
  clientIp?: string | null;
  userparams?: string | null;
  persParam?: string | null;
  sn?: string | null;
  enableSkills?: string[] | null;
}

export interface AIUISkillResult {
  raw: string;
  nlp: string;
  text: string;
  accepted: boolean;
  rc4: boolean;
  unsupportedSkill: boolean;
}

export type EmitPayload =
  | { tag: "text"; val: string }
  | { tag: "audio"; val: Uint8Array }
  | { tag: "emotion"; val: string }
  | { tag: "action"; val: { kind: string; data: string } }
  | { tag: "endSession"; val: string }
  | { tag: "raw"; val: string };

export interface HTTPChunk {
  status: number | null;
  headers: Array<[string, string]> | null;
  bodyPart: Uint8Array;
  done: boolean;
}

export interface HTTPStreamRequest {
  method: string;
  url: string;
  headers: Array<[string, string]>;
  body: Uint8Array | null;
  responseMode?: "stream" | "buffer";
  connectTimeoutMs?: number;
  firstByteTimeoutMs?: number;
  idleTimeoutMs?: number;
  totalTimeoutMs?: number;
  maxResponseBytes?: number;
}

export interface HTTPStreamHandlers {
  onHeaders?: (status: number, headers: Array<[string, string]>) => void;
  onChunk?: (data: Uint8Array) => void;
  onDone?: () => void;
  onError?: (error: AgentErrorObj) => void;
}

export type WSFrame =
  | { tag: "text"; val: string }
  | { tag: "binary"; val: Uint8Array }
  | { tag: "closed"; val: { code: number; reason: string } };

export interface AgentErrorObj { code: string; message: string; retryable: boolean; }

export interface LLMStreamEvents {
  onChunk?: (chunk: ChatChunk) => void;
  onDone?: () => void;
  onError?: (error: AgentErrorObj) => void;
}

export type LogFields = Record<string, unknown>;
export interface HistoryAppendOptions { last?: boolean; chatId?: string; msgType?: string; }

export interface ListenAIHost {
  // v1.0
  llmChat(req: ChatRequest): string;
  llmPoll(streamId: string): ChatChunk | null;
  llmSubmitToolResult(streamId: string, results: ToolResult[]): void;
  llmStart(req: ChatRequest, handlers: LLMStreamEvents): string;
  ttsSynthesize(req: TTSRequest): string;
  ttsPoll(streamId: string): { audio: Uint8Array; codec: string; done: boolean } | null;
  ttsOpen(req: TTSOpenRequest): TTSOpenResult;
  ttsSend(streamId: string, text: string): void;
  ttsClose(streamId: string): void;
  ttsCloseActive(): void;
  textStreamOpen(req: TextStreamOpenRequest): TextStreamOpenResult;
  textStreamSend(streamId: string, text: string): void;
  textStreamClose(streamId: string): void;
  textStreamCloseActive(): void;
  knowledgeQuery(req: KnowledgeQueryRequest): string;
  xiaolingAgentChat(req: XiaolingAgentRequest): string;
  xiaolingAgentPoll(streamId: string): XiaolingAgentChunk | null;
  aiuiSkill(req: AIUISkillRequest): AIUISkillResult;
  historyGet(sessionId: string, limit: number | null): ChatMessage[];
  historyAppend(sessionId: string, messages: ChatMessage | ChatMessage[], options?: HistoryAppendOptions): void;
  historyClear(sessionId: string): void;
  kvGet(key: string): string | null;
  kvSet(key: string, value: string, ttlSecs: number | null): void;
  secretSet(sessionId: string, key: string, value: string): void;
  secretGet(sessionId: string, key: string): string | null;
  secretDelete(sessionId: string, key: string): void;
  secretClear(sessionId: string): void;
  emit(sessionId: string, payload: EmitPayload): void;
  httpRequest(method: string, url: string, headers: Array<[string, string]>, body: string | null): string;
  log(level: "debug" | "info" | "warn" | "error", message: string, fields?: LogFields): void;
  // v1.1
  httpStream(method: string, url: string, headers: Array<[string, string]>, body: Uint8Array | null): string;
  httpStreamPoll(streamId: string): HTTPChunk | null;
  httpStreamStart(req: HTTPStreamRequest, handlers: HTTPStreamHandlers): string;
  httpStreamCancel(streamId: string): void;
  timerStart(delayMs: number, callback: () => void): string;
  timerCancel(timerId: string): void;
  wsConnect(url: string, headers: Array<[string, string]>): string;
  wsSend(streamId: string, frame: WSFrame): void;
  wsPoll(streamId: string): WSFrame | null;
  wsClose(streamId: string, code: number | null, reason: string | null): void;
  // helpers (not in WIT; see design §3.4)
  utf8Decode(data: Uint8Array): string;
  sleep(ms: number): void;
}

declare global { var host: ListenAIHost; }
