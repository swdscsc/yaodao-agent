import {
  CancellationTokenSource,
  log,
  normalizeClosedToolContent,
  type AgentChatMessage,
  type CancellationToken,
  type CompleteTurnRequest,
  type InteractionRecord,
  type RunResult,
} from "@listenai/agent-sdk";
import { runtimeClient } from "../context/listenaiContextProvider";
import {
  GENERATED_IMAGE_HISTORY_TEXT,
  mapImageArtifacts,
  persistenceSafeImageSource,
  type ImageArtifact,
} from "../image/imageArtifacts";
import type { HistoryProvider } from "../history/historyProvider";
import { requestContext, type VoiceTurnContext } from "../types";
import { parseContentChunks, type ContentMeta } from "../response/contentTagParser";
import { safeErrorFields } from "../errors/safeLogging";
import { boundedCurrentUserText } from "../text/utf8Budget";

export interface PersistenceInput {
  context: VoiceTurnContext;
  finalAnswer: string;
  runResult?: RunResult;
  historyMessages?: AgentChatMessage[];
  status: CompleteTurnRequest["status"];
  stopReason: CompleteTurnRequest["stop_reason"];
  error?: CompleteTurnRequest["error"];
  historyPolicy: CompleteTurnRequest["history_policy"];
  elapsedMs: number;
  imageArtifacts?: ImageArtifact[];
  historyProvider?: HistoryProvider;
  outputMeta?: ContentMeta;
  requestHistoryMessages?: AgentChatMessage[];
}

export interface PersistenceProvider {
  persist(input: PersistenceInput): Promise<void>;
}

export class ListenAIPersistenceProvider implements PersistenceProvider {
  async persist(input: PersistenceInput): Promise<void> {
    const interactionRecord = this.buildInteractionRecord(input);
    // Abnormal turns, including quota rejections, are recorded by Runtime
    // completion but must not pollute the conversational history.
    if (input.historyPolicy === "store" && (input.finalAnswer || hasImageOnlyResult(input))) {
      try {
        await this.appendHistory(input);
      } catch (error) {
        log.warn("history append failed", {
          turnId: input.context.turnId,
          ...safeErrorFields(error),
        });
      }
    }
    const scope = boundedPostTurnScope(10_000, input.context.cancellation);
    const context = { ...input.context, cancellation: scope.token };
    let persistedAgentVersion = input.context.config.agentJsVersion;
    if (
      input.context.config.agentBundleAppId &&
      input.context.config.businessAppId &&
      input.context.config.agentBundleAppId !== input.context.config.businessAppId &&
      input.context.config.xiaolingVersion
    ) {
      persistedAgentVersion = input.context.config.xiaolingVersion;
    }
    try {
      await runtimeClient(context).completeTurn(input.context.turnId, {
        status: input.status,
        stop_reason: input.stopReason,
        ...(input.error ? { error: input.error } : {}),
        ...(input.finalAnswer ? { final_answer: input.finalAnswer } : {}),
        history_policy: input.historyPolicy,
        timing: { total_ms: Math.max(0, Math.floor(input.elapsedMs)) },
        started_at: new Date(Date.now() - Math.max(0, Math.floor(input.elapsedMs))).toISOString(),
        ...(persistedAgentVersion ? { agent_js_version: persistedAgentVersion } : {}),
        ...(input.context.voiceProfileId ? { voice_profile_id: input.context.voiceProfileId } : {}),
        ...(input.runResult?.usage ? { model_usage: runtimeModelUsage(input.runResult.usage) } : {}),
        interaction_record: interactionRecord,
      }, requestContext(context, "complete"), scope.token);
    } catch (error) {
      log.warn("turn completion write failed", {
        turnId: input.context.turnId,
        ...safeErrorFields(error),
      });
    } finally {
      scope.close();
    }
  }

  private buildInteractionRecord(input: PersistenceInput): InteractionRecord {
    const requestMessages = (input.requestHistoryMessages ?? [])
      .map(toInteractionRecordMessage);
    requestMessages.push({
      role: "user",
      content: boundedCurrentUserText(input.context.userText),
    });

    const current = currentTurnMessages(input);
    const toolData = legacyToolHistoryData(
      current,
      input.runResult?.toolResults,
      mapImageArtifacts(input.imageArtifacts ?? input.runResult?.artifacts ?? []),
    );
    let responseMessages = toolData;
    if (responseMessages.length === 0) {
      responseMessages = current
        .filter((message) => message.role === "assistant" || message.role === "tool")
        .map(toInteractionRecordMessage);
    }
    const metaData = {
      ...(outputMetadata(input.outputMeta) ?? {}),
      ...(input.context.vprInfo ? { vpr_info: cloneValue(input.context.vprInfo) } : {}),
    };
    return {
      request: {
        ...(input.context.config.runtime.model.temperature !== undefined
          ? { temperature: input.context.config.runtime.model.temperature }
          : {}),
        messages: requestMessages,
      },
      response: {
        messages: responseMessages,
        ...(Object.keys(metaData).length > 0 ? { meta_data: metaData } : {}),
        ...(input.runResult ? {
          model_steps: input.runResult.modelSteps,
          tool_calls: input.runResult.toolCalls,
        } : {}),
      },
    };
  }

  private async appendHistory(input: PersistenceInput): Promise<void> {
    const msgType = input.historyPolicy === "abnormal" || hasPhotoOnlyResult(input) ? "2" : "1";
    const current = currentTurnMessages(input);
    const messages = legacyTurnHistoryMessages(current, input);
    const assistantMeta = messages[1]?.meta;
    const toolHistoryMessageCount = Array.isArray(assistantMeta?.data)
      ? assistantMeta.data.length
      : 0;
    log.info("official voice history append prepared", {
      turnId: input.context.turnId,
      topLevelMessageCount: messages.length,
      reactMessageCount: current.length,
      toolHistoryMessageCount,
      agentStop: input.runResult?.status === "AGENT_STOP",
    });
    const options = {
      chatId: input.context.turnId,
      msgType,
    };
    if (input.historyProvider) {
      await input.historyProvider.append(
        input.context.sessionId,
        messages as unknown as AgentChatMessage[],
        options,
        input.context.cancellation,
      );
      return;
    }
    const historyHost = host as unknown as ExtendedHistoryHost;
    historyHost.historyAppend(input.context.sessionId, messages, options);
  }
}

function runtimeModelUsage(usage: NonNullable<RunResult["usage"]>): NonNullable<CompleteTurnRequest["model_usage"]> {
  return {
    prompt_tokens: usage.promptTokens,
    completion_tokens: usage.completionTokens,
    total_tokens: usage.totalTokens,
    ...(usage.cachedPromptTokens !== undefined
      ? { prompt_tokens_details: { cached_tokens: usage.cachedPromptTokens } }
      : {}),
  };
}

// /v2/sessions stores one user/assistant pair per turn. The reader expands the
// nested ReAct chain; media remains in the tool-result JSON while the final
// assistant message is projected to text for the main model.
function legacyTurnHistoryMessages(
  current: AgentChatMessage[],
  input: PersistenceInput,
): HostHistoryMessage[] {
  const user = current.find((message) => message.role === "user") ?? {
    role: "user" as const,
    content: boundedCurrentUserText(input.context.userText),
  };
  const toolData = legacyToolHistoryData(
    current,
    input.runResult?.toolResults,
    mapImageArtifacts(input.imageArtifacts ?? input.runResult?.artifacts ?? []),
  );
  const assistantMeta: Record<string, unknown> = {
    ...(outputMetadata(input.outputMeta) ?? {}),
    ...(toolData.length > 0 ? { type: "tool_call", data: toolData } : {}),
  };
  const cameraImage = currentTurnCameraImage(input);
  const historyUser = cameraImage
    ? {
      ...user,
      content: [
        { type: "text", text: boundedCurrentUserText(input.context.userText) },
        { type: "image_url", image_url: { url: cameraImage } },
      ],
    }
    : user;
  return [
    toHostHistoryMessage(historyUser, vprMetadata(input.context)),
    toHostHistoryMessage({
      role: "assistant",
      content: visibleHistoryAnswer(current, input.finalAnswer),
    }, Object.keys(assistantMeta).length > 0 ? assistantMeta : undefined),
  ];
}

function currentTurnCameraImage(input: PersistenceInput): string {
  const sources: string[] = [];
  const historyMessages = input.historyMessages ?? [];
  for (let index = historyMessages.length - 1; index >= 0; index -= 1) {
    const message = historyMessages[index];
    if (message.role !== "user") continue;
    if (!Array.isArray(message.content)) break;
    for (const item of message.content) {
      if (!isRecord(item) || item.type !== "image_url" || !isRecord(item.image_url)) continue;
      if (typeof item.image_url.url === "string") sources.push(item.image_url.url);
    }
    break;
  }
  for (const artifact of mapImageArtifacts(input.imageArtifacts ?? input.runResult?.artifacts ?? [])) {
    if (artifact.kind === "camera" && artifact.data) sources.push(artifact.data);
  }
  for (const source of sources) {
    const normalized = normalizeClosedToolContent({
      type: "image",
      kind: "camera",
      data: source,
    });
    if (normalized?.type !== "image" || !normalized.data) continue;
    return normalized.data;
  }
  return "";
}

function visibleHistoryAnswer(
  current: AgentChatMessage[],
  finalAnswer: string,
): AgentChatMessage["content"] {
  for (let index = current.length - 1; index >= 0; index -= 1) {
    const message = current[index];
    if (message.role !== "assistant" || message.toolCalls?.length) continue;
    if (Array.isArray(message.content)) return cloneMessages(message.content);
    break;
  }
  return finalAnswer;
}

function legacyToolHistoryData(
  current: AgentChatMessage[],
  toolResults: RunResult["toolResults"],
  imageArtifacts: ImageArtifact[],
): Array<Record<string, unknown>> {
  if (!current.some((message) => message.role === "assistant" && message.toolCalls?.length)) {
    return [];
  }
  const data: Array<Record<string, unknown>> = [];
  const resultsByCallID = new Map((toolResults ?? []).map((result) => [result.callId, result]));
  let currentUserSeen = false;
  let earlierAssistantText = "";
  for (const message of current) {
    if (message.role === "user") {
      currentUserSeen = true;
      continue;
    }
    if (!currentUserSeen || (message.role !== "assistant" && message.role !== "tool")) continue;
    let content = message.content;
    if (message.role === "tool" && message.toolCallId && resultsByCallID.has(message.toolCallId)) {
      content = legacyToolResultContent(
        resultsByCallID.get(message.toolCallId)!,
        message.content,
        message.name,
        imageArtifacts,
      );
    }
    if (message.role === "assistant" && Array.isArray(content)) {
      let text = structuredContentText(content);
      if (earlierAssistantText && text.startsWith(earlierAssistantText)) {
        text = text.slice(earlierAssistantText.length);
      }
      content = text;
    }
    const item: Record<string, unknown> = {
      role: message.role,
      content,
    };
    if (message.role === "assistant" && message.toolCalls?.length) {
      item.tool_calls = cloneMessages(message.toolCalls);
      earlierAssistantText += typeof content === "string" ? content : "";
    }
    if (message.role === "tool") {
      if (message.toolCallId) item.tool_call_id = message.toolCallId;
      if (message.name) item.name = message.name;
    }
    data.push(item);
  }
  return data;
}

function legacyToolResultContent(
  result: NonNullable<RunResult["toolResults"]>[number],
  fallback: AgentChatMessage["content"],
  toolName: string | undefined,
  imageArtifacts: ImageArtifact[],
): string {
  const content = result.content.flatMap((item): Array<Record<string, unknown>> => item.type === "text" && item.text
    ? [{ type: "text", text: item.text }]
    : []);
  const textIsEmpty = content.length === 0;
  if (textIsEmpty && typeof fallback === "string" && fallback) {
    content.push({ type: "text", text: fallback });
  }
  if (textIsEmpty && result.artifacts?.length) {
    content.push(...cloneMessages(result.artifacts) as unknown as Array<Record<string, unknown>>);
  }
  const images = legacyToolImages(result, toolName, imageArtifacts);
  if (images.length > 0) {
    return JSON.stringify({
      message: {
        ...(result.control.agentStop ? { agent_stop: true } : {}),
        content: [...content, ...images],
      },
    });
  }
  return JSON.stringify({
    message: {
      agent_stop: result.control.agentStop,
      content,
    },
    isError: result.isError,
    control: result.control,
  });
}

function legacyToolImages(
  result: NonNullable<RunResult["toolResults"]>[number],
  toolName: string | undefined,
  imageArtifacts: ImageArtifact[],
): Array<Record<string, unknown>> {
  const inferredKind = legacyToolImageKind(toolName);
  const resultImages = result.content.flatMap((item): ImageArtifact[] => item.type === "image"
    ? [{
      type: "image",
      kind: item.kind,
      ...(item.url ? { url: item.url } : {}),
      ...(item.data ? { data: item.data } : {}),
    }]
    : []);
  const candidates = resultImages.length > 0
    ? resultImages
    : inferredKind
      ? imageArtifacts.filter((artifact) => artifact.kind === inferredKind)
      : [];
  const seen = new Set<string>();
  return candidates
    .flatMap((artifact) => {
      const source = persistenceSafeImageSource(artifact);
      if (!source) return [];
      const kind = artifact.kind === "unknown" ? inferredKind : artifact.kind;
      const identity = `${kind}\u0000${source}`;
      if (seen.has(identity)) return [];
      seen.add(identity);
      return [{
        type: "image",
        ...(kind === "camera" ? { data: source } : { image: source }),
      }];
    });
}

function legacyToolImageKind(toolName: string | undefined): ImageArtifact["kind"] | undefined {
  const normalized = String(toolName || "").toLowerCase();
  if (normalized.includes("take_photo") || normalized.includes("camera")) return "camera";
  if (normalized.includes("edit_image")) return "edited";
  if (normalized.includes("draw_image") || normalized.includes("my_image")) return "generated";
  return undefined;
}

function structuredContentText(content: Array<Record<string, unknown>>): string {
  return content
    .filter((item) => item.type === "text" && typeof item.text === "string")
    .map((item) => item.text as string)
    .join("");
}

function toInteractionRecordMessage(message: AgentChatMessage): Record<string, unknown> {
  const raw = message as unknown as Record<string, unknown>;
  const output: Record<string, unknown> = {
    role: message.role,
    content: cloneValue(message.content),
  };
  const name = message.name ?? raw.name;
  const toolCallId = message.toolCallId ?? raw.tool_call_id;
  const toolCalls = message.toolCalls ?? raw.tool_calls;
  if (typeof name === "string" && name) output.name = name;
  if (typeof toolCallId === "string" && toolCallId) output.tool_call_id = toolCallId;
  if (Array.isArray(toolCalls) && toolCalls.length > 0) output.tool_calls = cloneMessages(toolCalls);
  if (isRecord(raw.meta) && Object.keys(raw.meta).length > 0) output.meta = cloneValue(raw.meta);
  return output;
}

function outputMetadata(meta: ContentMeta | undefined): Record<string, unknown> | undefined {
  if (!meta) return undefined;
  const output: Record<string, unknown> = {};
  if (meta.emotion) output.emotion = meta.emotion;
  if (meta.language) output.language = meta.language;
  return Object.keys(output).length > 0 ? output : undefined;
}

function boundedPostTurnScope(timeoutMs: number, parent: CancellationToken): {
  token: CancellationToken;
  close(): void;
} {
  const source = new CancellationTokenSource();
  const unsubscribeParent = parent.onCancel((reason) => {
    source.cancel(reason || "Parent turn cancelled");
  });
  const timerId = host.timerStart(timeoutMs, () => source.cancel("Post-turn persistence timed out"));
  let closed = false;
  return {
    token: source.token,
    close(): void {
      if (closed) return;
      closed = true;
      unsubscribeParent();
      host.timerCancel(timerId);
    },
  };
}

export function currentTurnMessages(input: PersistenceInput): AgentChatMessage[] {
  let messages: AgentChatMessage[];
  if (input.historyMessages) {
    messages = cloneMessages(input.historyMessages);
    boundLastUserMessage(messages, input.context.userText);
    return sanitizeStructuredImageHistory(applyImageHistory(messages, input));
  }
  if (input.runResult) {
    const runMessages = input.runResult.messages;
    let currentUserIndex = -1;
    for (let index = runMessages.length - 1; index >= 0; index -= 1) {
      const message = runMessages[index];
      if (message.role === "user") {
        currentUserIndex = index;
        break;
      }
    }
    if (currentUserIndex >= 0) {
      const current = cloneMessages(runMessages.slice(currentUserIndex));
      boundLastUserMessage(current, input.context.userText);
      const earlierVisibleText = current
        .filter((message) => message.role === "assistant" && message.toolCalls?.length)
        .map((message) => visibleAssistantText(message.content))
        .join("");
      for (let index = current.length - 1; index >= 0; index -= 1) {
        const message = current[index];
        if (message.role === "assistant" && !message.toolCalls?.length) {
          message.content = earlierVisibleText && input.finalAnswer.startsWith(earlierVisibleText)
            ? input.finalAnswer.slice(earlierVisibleText.length)
            : earlierVisibleText
              ? visibleAssistantText(message.content)
              : input.finalAnswer;
          break;
        }
      }
      return sanitizeStructuredImageHistory(applyImageHistory(current, input));
    }
  }
  messages = [
    { role: "user", content: boundedCurrentUserText(input.context.userText) },
    { role: "assistant", content: input.finalAnswer },
  ];
  return sanitizeStructuredImageHistory(applyImageHistory(messages, input));
}

function boundLastUserMessage(messages: AgentChatMessage[], text: string): void {
  for (let index = messages.length - 1; index >= 0; index -= 1) {
    const message = messages[index];
    if (message.role !== "user") continue;
    const bounded = boundedCurrentUserText(text);
    if (typeof message.content === "string") {
      message.content = bounded;
      return;
    }
    if (!Array.isArray(message.content)) {
      message.content = bounded;
      return;
    }
    const content: Array<Record<string, unknown>> = [];
    let textWritten = false;
    for (const item of message.content) {
      if (isRecord(item) && item.type === "text") {
        if (!textWritten) content.push({ ...item, text: bounded });
        textWritten = true;
      } else if (isRecord(item)) {
        content.push(item);
      }
    }
    if (!textWritten) content.unshift({ type: "text", text: bounded });
    message.content = content;
    return;
  }
}

function sanitizeStructuredImageHistory(messages: AgentChatMessage[]): AgentChatMessage[] {
  for (const message of messages) {
    if (!Array.isArray(message.content)) continue;
    const content: Array<Record<string, unknown>> = [];
    for (const item of message.content) {
      if (!isRecord(item) || item.type !== "image_url") {
        if (isRecord(item)) content.push(item);
        continue;
      }
      const imageURL = isRecord(item.image_url) ? item.image_url.url : undefined;
      const safe = typeof imageURL === "string"
        ? persistenceSafeImageSource({ type: "image", kind: "input", url: imageURL })
        : "";
      if (safe) content.push({ type: "image_url", image_url: { url: safe } });
    }
    message.content = content;
  }
  return messages;
}

function visibleAssistantText(content: AgentChatMessage["content"]): string {
  return typeof content === "string" ? parseContentChunks([content]).text : "";
}

function applyImageHistory(messages: AgentChatMessage[], input: PersistenceInput): AgentChatMessage[] {
  const images = mapImageArtifacts(input.imageArtifacts ?? input.runResult?.artifacts ?? []);
  const camera = images.filter((artifact) => artifact.kind === "camera");
  const generated = images.filter((artifact) => artifact.kind === "generated" || artifact.kind === "edited");
  if (camera.length > 0) {
    const user = messages.find((message) => message.role === "user");
    if (user) user.content = structuredImageContent(boundedCurrentUserText(input.context.userText), camera);
  }
  if (generated.length > 0) {
    let assistant: AgentChatMessage | undefined;
    for (let index = messages.length - 1; index >= 0; index -= 1) {
      if (messages[index].role === "assistant" && !messages[index].toolCalls?.length) {
        assistant = messages[index];
        break;
      }
    }
    const content = structuredImageContent(input.finalAnswer || GENERATED_IMAGE_HISTORY_TEXT, generated);
    if (assistant) assistant.content = content;
    else messages.push({ role: "assistant", content });
  }
  return messages;
}

function structuredImageContent(text: string, images: ImageArtifact[]): Array<Record<string, unknown>> {
  const safeSources = images
    .map(persistenceSafeImageSource)
    .filter(Boolean);
  return [
    { type: "text", text },
    ...safeSources.map((source) => ({
      type: "image_url",
      image_url: { url: source },
    })),
  ];
}

function hasPhotoOnlyResult(input: PersistenceInput): boolean {
  return !input.finalAnswer && (input.imageArtifacts ?? []).some((artifact) => artifact.kind === "camera");
}

function hasImageOnlyResult(input: PersistenceInput): boolean {
  return !input.finalAnswer && (input.imageArtifacts ?? []).some((artifact) => (
    artifact.kind === "camera" || artifact.kind === "generated" || artifact.kind === "edited"
  ));
}

interface HostHistoryMessage {
  role: string;
  content: AgentChatMessage["content"];
  toolCallId: string | null;
  toolCalls?: AgentChatMessage["toolCalls"];
  meta?: Record<string, unknown>;
}

interface ExtendedHistoryHost {
  historyAppend(
    sessionId: string,
    messages: HostHistoryMessage[],
    options?: { last?: boolean; chatId?: string; msgType?: string },
  ): void;
}

function toHostHistoryMessage(message: AgentChatMessage, turnMeta?: Record<string, unknown>): HostHistoryMessage {
  const meta: Record<string, unknown> = { ...(turnMeta ?? {}) };
  if (message.name) meta.name = message.name;
  return {
    role: message.role,
    content: message.content,
    toolCallId: message.toolCallId ?? null,
    ...(message.toolCalls?.length ? { toolCalls: cloneMessages(message.toolCalls) } : {}),
    ...(Object.keys(meta).length > 0 ? { meta } : {}),
  };
}

function vprMetadata(context: VoiceTurnContext): Record<string, unknown> | undefined {
  const meta: Record<string, unknown> = {};
  if (context.voiceProfileId) meta.vpr_feature_id = context.voiceProfileId;
  if (context.vprInfo) meta.vpr_info = JSON.parse(JSON.stringify(context.vprInfo)) as Record<string, unknown>;
  return Object.keys(meta).length > 0 ? meta : undefined;
}

function cloneMessages<T>(messages: T[]): T[] {
  return cloneValue(messages);
}

function cloneValue<T>(value: T): T {
  return JSON.parse(JSON.stringify(value)) as T;
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}
