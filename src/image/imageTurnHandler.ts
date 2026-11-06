import type {
  AgentChatMessage,
  ChatModel,
  ModelUsage,
} from "@listenai/agent-sdk";
import {
  AgentError,
  asAgentError,
  HTTPJSONClient,
  normalizeClosedToolContent,
  type HTTPJSONHeaders,
  type ModelRequest,
} from "@listenai/agent-sdk";
import type { ModelResolver } from "../model/configModelResolver";
import type { VoiceTurnContext } from "../types";
import { OFFICIAL_DEFAULT_VISION_MODEL } from "../config/legacyConfigAdapter";
import { IMAGE_FALLBACK_REPLY } from "../routing/phrases";
import { boundedCurrentUserText } from "../text/utf8Budget";
import { safeModelRequestLog } from "../observability/turnLogger";

export interface ImageTurnResult {
  answer: string;
  messages: AgentChatMessage[];
  usage?: ModelUsage;
}

export interface ImageTurnHandler {
  run(
    context: VoiceTurnContext,
    image: string,
    modelResolver: ModelResolver,
    onDelta: (text: string) => void,
  ): Promise<ImageTurnResult>;
}

export class DefaultImageTurnHandler implements ImageTurnHandler {
  async run(
    context: VoiceTurnContext,
    image: string,
    modelResolver: ModelResolver,
    onDelta: (text: string) => void,
  ): Promise<ImageTurnResult> {
    const normalizedImage = normalizeImageSource(image);
    const config = context.config.runtime.model;
    const provider = config.sidecars?.vision
      ?? { type: "platform", model: OFFICIAL_DEFAULT_VISION_MODEL };
    const primary = modelResolver.resolveProvider(context, provider);
    const fallback = config.fallback
      ? modelResolver.resolveProvider(context, config.fallback)
      : undefined;
    const candidates: Array<{ model: ChatModel; modelName: string }> = [];
    for (let attempt = 0; attempt <= boundedRetries(config.maxRetries); attempt += 1) {
      candidates.push(primary);
    }
    if (fallback) candidates.push(fallback);
    const messages = imageMessages(context.userText, normalizedImage);
    let visibleOutput = false;
    let lastError: AgentError | undefined;
    const totalTimeoutMs = config.timeoutMs ?? 120_000;
    for (let index = 0; index < candidates.length; index += 1) {
      context.cancellation.throwIfCancelled();
      const candidate = candidates[index];
      let usage: ModelUsage | undefined;
      try {
        const requestId = `${context.requestId}:vision:${index + 1}`;
        const request: ModelRequest = {
          modelCallId: `${context.turnId}:vision:${index + 1}`,
          purpose: "vision",
          model: candidate.modelName,
          messages,
          temperature: config.temperature,
          maxTokens: config.maxTokens,
          firstFrameTimeoutMs: Math.min(totalTimeoutMs, 15_000),
          idleTimeoutMs: Math.min(totalTimeoutMs, 30_000),
          totalTimeoutMs,
        };
        safeModelRequestLog("official voice vision model request", context, requestId, request, {
          attempt: index + 1,
          candidateModel: candidate.modelName,
        });
        const handle = candidate.model.run(request, {
          onTextDelta(text): void {
            if (text) visibleOutput = true;
            onDelta(text);
          },
          onUsage(value): void { usage = value; },
        }, {
          sessionId: context.sessionId,
          turnId: context.turnId,
          appId: context.config.businessAppId,
          requestId,
          cancellation: context.cancellation,
        });
        const result = await handle.completed;
        return { answer: result.text, messages, ...(usage ? { usage } : {}) };
      } catch (error) {
        lastError = asAgentError(error);
        if (lastError.code === "AGENT_RESOURCE_FORBIDDEN") {
          onDelta(IMAGE_FALLBACK_REPLY);
          return { answer: IMAGE_FALLBACK_REPLY, messages };
        }
        if (visibleOutput || !lastError.retryable || index === candidates.length - 1) throw lastError;
      }
    }
    throw lastError ?? new AgentError("AGENT_UPSTREAM_ERROR", "Vision model request failed", {
      retryable: true,
      phase: "model",
    });
  }
}

export interface HTTPImageTurnHandlerOptions {
  url: string;
  headers?: HTTPJSONHeaders;
  timeoutMs?: number;
  maxResponseBytes?: number;
  body?: (input: { text: string; image: string }, context: VoiceTurnContext) => unknown;
  extractText: (response: unknown, context: VoiceTurnContext) => string;
}

/** Adapter for a developer-owned HTTP image understanding service. */
export class HTTPImageTurnHandler implements ImageTurnHandler {
  private readonly client: HTTPJSONClient;

  constructor(private readonly options: HTTPImageTurnHandlerOptions, client?: HTTPJSONClient) {
    this.client = client ?? new HTTPJSONClient();
  }

  async run(
    context: VoiceTurnContext,
    image: string,
    _modelResolver: ModelResolver,
    onDelta: (text: string) => void,
  ): Promise<ImageTurnResult> {
    const normalizedImage = normalizeImageSource(image);
    const response = await this.client.request(
      {
        method: "POST",
        url: this.options.url,
        headers: this.options.headers,
        body: this.options.body?.({
          text: boundedCurrentUserText(context.userText),
          image: normalizedImage,
        }, context) ?? {
          text: boundedCurrentUserText(context.userText),
          image: normalizedImage,
        },
        timeoutMs: this.options.timeoutMs ?? 30_000,
        maxResponseBytes: this.options.maxResponseBytes ?? 4 << 20,
      },
      context.cancellation,
    );
    const answer = this.options.extractText(response, context);
    if (answer) onDelta(answer);
    return {
      answer,
      messages: imageMessages(context.userText, normalizedImage),
    };
  }
}

function normalizeImageSource(value: string): string {
  const normalized = normalizeClosedToolContent(value.startsWith("data:")
    ? { type: "image", kind: "input", data: value }
    : { type: "image", kind: "input", url: value });
  if (!normalized || normalized.type !== "image") {
    throw new AgentError("AGENT_IMAGE_SOURCE_INVALID", "Image source is not allowed", {
      phase: "config",
    });
  }
  return normalized.url ?? normalized.data!;
}

function boundedRetries(value?: number): number {
  return Number.isInteger(value) && Number(value) > 0 ? Math.min(Number(value), 3) : 0;
}

function imageMessages(text: string, image?: string): AgentChatMessage[] {
  return [{
    role: "user",
    content: [
      { type: "text", text: boundedCurrentUserText(text) },
      ...(image ? [{ type: "image_url", image_url: { url: image } }] : []),
    ],
  }];
}
