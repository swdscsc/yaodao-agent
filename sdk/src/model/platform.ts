import { AgentRuntimeTransport } from "../transport/agentRuntime";
import { runOpenAIStream } from "./openaiStream";
import type {
  ChatMessage,
  ChatModel,
  ModelRequest,
  ModelRunContext,
  ModelRunHandle,
  ModelStreamHandlers,
} from "./types";

export interface PlatformChatModelOptions {
  baseUrl: string;
  tokenSecretKey: string;
}

export class PlatformChatModel implements ChatModel {
  readonly id = "listenai-platform";
  private readonly transport: AgentRuntimeTransport;

  constructor(options: PlatformChatModelOptions) {
    this.transport = new AgentRuntimeTransport(options);
  }

  run(request: ModelRequest, handlers: ModelStreamHandlers, context: ModelRunContext): ModelRunHandle {
    const body = {
      model_call_id: request.modelCallId,
      purpose: request.purpose,
      model: request.model,
      messages: request.messages.map(toWireMessage),
      tools: request.tools,
      tool_choice: request.toolChoice,
      temperature: request.temperature,
      max_tokens: request.maxTokens,
      // Platform models must return only the visible answer by default.
      thinking: { type: "disabled" },
      stream: true,
    };
    return runOpenAIStream(request.modelCallId, handlers, (httpHandlers) => this.transport.stream({
      path: "/model/chat/completions",
      body,
      context,
      firstByteTimeoutMs: request.firstFrameTimeoutMs,
      idleTimeoutMs: request.idleTimeoutMs,
      totalTimeoutMs: request.totalTimeoutMs ?? request.timeoutMs,
    }, httpHandlers, context.cancellation), {
      trustedErrorPayload: true,
    });
  }
}

export function toWireMessage(message: ChatMessage): Record<string, unknown> {
  const wire: Record<string, unknown> = {
    role: message.role,
    content: message.content,
  };
  if (message.name) wire.name = message.name;
  if (message.toolCallId) wire.tool_call_id = message.toolCallId;
  if (message.toolCalls) wire.tool_calls = message.toolCalls;
  return wire;
}
