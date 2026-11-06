import type { CancellationToken } from "../runtime/cancellation";
import type { AgentError } from "../runtime/errors";

export type ContentPart = Record<string, unknown>;
export type ChatMessageContent = string | ContentPart[] | null;

export interface AssistantToolCall {
  id: string;
  type: "function";
  function: {
    name: string;
    arguments: string;
  };
}

export interface ChatMessage {
  role: "system" | "user" | "assistant" | "tool";
  content: ChatMessageContent;
  name?: string;
  toolCallId?: string;
  toolCalls?: AssistantToolCall[];
}

export interface FunctionTool {
  type: "function";
  function: {
    name: string;
    description?: string;
    parameters: Record<string, unknown>;
  };
}

export type ToolChoice = "none" | "auto" | "required" | Record<string, unknown>;

export interface ModelUsage {
  promptTokens: number;
  completionTokens: number;
  totalTokens: number;
  cachedPromptTokens?: number;
}

export interface ToolCallDelta {
  index: number;
  id?: string;
  name?: string;
  arguments?: string;
}

export interface ModelRequest {
  modelCallId: string;
  purpose: "chat" | "emotion" | "memory" | "preference" | "vision";
  model: string;
  messages: ChatMessage[];
  tools?: FunctionTool[];
  toolChoice?: ToolChoice;
  temperature?: number;
  maxTokens?: number;
  firstFrameTimeoutMs?: number;
  idleTimeoutMs?: number;
  totalTimeoutMs?: number;
  /** @deprecated Use totalTimeoutMs. */
  timeoutMs?: number;
}

export interface ModelStreamHandlers {
  onTextDelta?: (delta: string) => void;
  onToolCallDelta?: (delta: ToolCallDelta) => void;
  onUsage?: (usage: ModelUsage) => void;
  onFinish?: (reason: string) => void;
  onError?: (error: AgentError) => void;
}

export interface ModelRunContext {
  sessionId: string;
  turnId?: string;
  requestId: string;
  toolCallId?: string;
  appId?: string;
  cancellation: CancellationToken;
}

export interface ModelRunResult {
  text: string;
  toolCalls: AssistantToolCall[];
  usage?: ModelUsage;
  finishReason: string;
}

export interface ModelRunHandle {
  id: string;
  completed: Promise<ModelRunResult>;
  cancel(reason?: string): void;
}

export interface ChatModel {
  readonly id: string;
  run(
    request: ModelRequest,
    handlers: ModelStreamHandlers,
    context: ModelRunContext,
  ): ModelRunHandle;
}
