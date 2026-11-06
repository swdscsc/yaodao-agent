import {
  AgentCancelledError,
  HTTPJSONClient,
  type HTTPJSONHeaders,
} from "@listenai/agent-sdk";
import { runtimeClient } from "../context/listenaiContextProvider";
import { requestContext, type VoiceTurnContext } from "../types";
import { isOptionalDependencyError } from "../errors/optionalDependency";

export interface KnowledgeResult {
  promptContent: string;
  faqDirectReply: boolean;
  response?: unknown;
  frames: Array<Record<string, unknown>>;
  warnings: string[];
}

export interface KnowledgeProvider {
  query(context: VoiceTurnContext): Promise<KnowledgeResult>;
}

export class ListenAIKnowledgeProvider implements KnowledgeProvider {
  async query(context: VoiceTurnContext): Promise<KnowledgeResult> {
    try {
      const response = await runtimeClient(context).queryKnowledge({
        query: context.userText,
      }, requestContext(context, "knowledge"), context.cancellation);
      return {
        promptContent: response.knowledge_text,
        faqDirectReply: response.faq_direct_reply === true,
        response,
        frames: [],
        warnings: response.warnings.map((warning) => warning.code),
      };
    } catch (error) {
      if (!isOptionalDependencyError(error)) throw error;
      return { promptContent: "", faqDirectReply: false, frames: [], warnings: ["knowledge.unavailable"] };
    }
  }
}

export interface HTTPKnowledgeProviderOptions {
  url: string;
  headers?: HTTPJSONHeaders;
  timeoutMs?: number;
  maxResponseBytes?: number;
  body?: (query: string, context: VoiceTurnContext) => unknown;
  extractText: (response: unknown, query: string) => string;
}

/** Adapter for a developer-owned HTTP knowledge service. */
export class HTTPKnowledgeProvider implements KnowledgeProvider {
  private readonly client: HTTPJSONClient;

  constructor(private readonly options: HTTPKnowledgeProviderOptions, client?: HTTPJSONClient) {
    this.client = client ?? new HTTPJSONClient();
  }

  async query(context: VoiceTurnContext): Promise<KnowledgeResult> {
    try {
      const response = await this.client.request(
        {
          method: "POST",
          url: this.options.url,
          headers: this.options.headers,
          body: this.options.body?.(context.userText, context)
            ?? { query: context.userText },
          timeoutMs: this.options.timeoutMs ?? 2_000,
          maxResponseBytes: this.options.maxResponseBytes ?? 1 << 20,
        },
        context.cancellation,
      );
      return {
        promptContent: this.options.extractText(response, context.userText),
        faqDirectReply: false,
        response,
        frames: [],
        warnings: [],
      };
    } catch (error) {
      if (error instanceof AgentCancelledError) throw error;
      return {
        promptContent: "",
        faqDirectReply: false,
        frames: [],
        warnings: ["knowledge.http_unavailable"],
      };
    }
  }
}
