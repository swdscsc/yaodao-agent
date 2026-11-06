import {
  HTTPJSONClient,
  uncancelledToken,
  type AgentChatMessage,
  type CancellationToken,
  type ChatMessage as HostChatMessage,
  type HTTPJSONRequest,
} from "@listenai/agent-sdk";
import type { VoiceTurnContext } from "../types";

export interface HistoryAppendOptions {
  last?: boolean;
  chatId?: string;
  msgType?: string;
}

export interface HistoryProvider {
  load(context: VoiceTurnContext): Promise<AgentChatMessage[]>;
  append(sessionId: string, messages: AgentChatMessage[], options?: HistoryAppendOptions, cancellation?: CancellationToken): Promise<void> | void;
  clear(sessionId: string, cancellation?: CancellationToken): Promise<void> | void;
}

export class HostHistoryProvider implements HistoryProvider {
  load(context: VoiceTurnContext): Promise<AgentChatMessage[]> {
    return Promise.resolve(host.historyGet(context.sessionId, 800) as AgentChatMessage[]);
  }

  append(sessionId: string, messages: AgentChatMessage[], options?: HistoryAppendOptions): void {
    host.historyAppend(sessionId, messages as unknown as HostChatMessage[], options);
  }

  clear(sessionId: string): void {
    host.historyClear(sessionId);
  }
}

export interface HTTPHistoryProviderOptions {
  client?: HTTPJSONClient;
  load: (context: VoiceTurnContext) => HTTPJSONRequest;
  append: (input: {
    sessionId: string;
    messages: AgentChatMessage[];
    options?: HistoryAppendOptions;
  }) => HTTPJSONRequest;
  clear: (sessionId: string) => HTTPJSONRequest;
  readMessages?: (response: unknown) => AgentChatMessage[];
}

/** Adapter for a developer-owned HTTP conversation history service. */
export class HTTPHistoryProvider implements HistoryProvider {
  private readonly client: HTTPJSONClient;
  private readonly options: HTTPHistoryProviderOptions;

  constructor(options: HTTPHistoryProviderOptions) {
    this.client = options.client ?? new HTTPJSONClient();
    this.options = options;
  }

  async load(context: VoiceTurnContext): Promise<AgentChatMessage[]> {
    const response = await this.client.request<unknown>(this.options.load(context), context.cancellation);
    return this.options.readMessages?.(response) ?? defaultReadMessages(response);
  }

  async append(sessionId: string, messages: AgentChatMessage[], options?: HistoryAppendOptions, cancellation?: CancellationToken): Promise<void> {
    await this.client.request(this.options.append({ sessionId, messages, options }), cancellation ?? uncancelledToken);
  }

  async clear(sessionId: string, cancellation?: CancellationToken): Promise<void> {
    await this.client.request(this.options.clear(sessionId), cancellation ?? uncancelledToken);
  }
}

function defaultReadMessages(value: unknown): AgentChatMessage[] {
  if (Array.isArray(value)) return value as AgentChatMessage[];
  if (isRecord(value) && Array.isArray(value.messages)) return value.messages as AgentChatMessage[];
  return [];
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}
