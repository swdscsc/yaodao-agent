import {
  CancellationTokenSource,
  DefaultReActEngine,
  ToolRegistry,
  asAgentError,
  closeActiveTextStream,
  closeActiveTTSStream,
  emitNLPFinish,
  log,
  type Agent,
  type AgentChatMessage,
  type ChatMessage as HostChatMessage,
  type DeviceMessage,
  type ReActEngine,
  type RunResult,
} from "@listenai/agent-sdk";
import {
  HostSessionConfigStore,
  type SessionConfigStore,
} from "./config/sessionConfigStore";
import {
  DefaultTurnRouter,
  type TurnRouter,
} from "./routing/turnRouter";
import {
  CLEAR_REPLY,
  EXIT_REPLY,
  UPLOAD_LOG_REPLY,
  WAKE_REPLIES,
} from "./routing/phrases";
import {
  DefaultResponsePipelineProvider,
  type ResponsePipeline,
  type ResponsePipelineProvider,
} from "./response/deviceResponsePipeline";
import { buildExitFrame } from "./tools/deviceFrameAdapter";
import {
  ListenAIContextProvider,
  type ContextProvider,
} from "./context/listenaiContextProvider";
import {
  DefaultPromptBuilder,
  type PromptBuilder,
} from "./prompt/defaultPromptBuilder";
import {
  ConfigModelResolver,
  type ModelResolver,
} from "./model/configModelResolver";
import {
  ListenAIKnowledgeProvider,
  type KnowledgeProvider,
} from "./knowledge/listenaiKnowledgeProvider";
import {
  ListenAIMemoryProvider,
  type MemoryProvider,
} from "./memory/listenaiMemoryProvider";
import {
  HostHistoryProvider,
  type HistoryProvider,
} from "./history/historyProvider";
import {
  DefaultToolProvider,
  type PreparedTools,
  type ToolProvider,
} from "./tools/defaultToolProvider";
import {
  ListenAIAiuiProvider,
  type AiuiProvider,
} from "./aiui/aiuiProvider";
import {
  DefaultImageTurnHandler,
  type ImageTurnHandler,
} from "./image/imageTurnHandler";
import {
  imageArtifactSource,
  mapToolImageArtifacts,
} from "./image/imageArtifacts";
import {
  ListenAIPersistenceProvider,
  type PersistenceInput,
  type PersistenceProvider,
} from "./persistence/persistenceProvider";
import {
  DefaultEmotionProvider,
  DEBUG_EMOTION_FEATURE,
  type EmotionProvider,
} from "./emotion/emotionProvider";
import {
  DefaultLimitPresenter,
  type LimitPresenter,
} from "./limits/limitPresenter";
import {
  StructuredTurnLogger,
  type TurnLogger,
} from "./observability/turnLogger";
import { mapAgentErrorStop } from "./response/stopReasonMapper";
import { mergePreparedNluContext } from "./context/contextMerger";
import type { NormalizedSessionConfig } from "./config/schema";
import {
  disabledRuntimeMemoryPolicy,
  parseRuntimeMemoryPolicy,
} from "./memory/runtimeMemoryPolicy";
import { safeErrorCode, safeErrorFields } from "./errors/safeLogging";
import {
  MAX_HISTORY_FETCH_MESSAGES,
  projectHistoryForTextModel,
  selectRecentHistory,
} from "./history/historyPolicy";
import {
  disabledServerDsaPolicy,
  parseServerDsaPolicy,
} from "./tools/dsaPolicy";
import { uuidV4, type VoiceTurnContext } from "./types";
import { boundedCurrentUserText, stripHTMLTags } from "./text/utf8Budget";

export interface OfficialVoiceAgentModules {
  configStore: SessionConfigStore;
  router: TurnRouter;
  contextProvider: ContextProvider;
  promptBuilder: PromptBuilder;
  modelResolver: ModelResolver;
  knowledgeProvider: KnowledgeProvider;
  memoryProvider: MemoryProvider;
  historyProvider: HistoryProvider;
  toolProvider: ToolProvider;
  aiuiProvider: AiuiProvider;
  imageHandler: ImageTurnHandler;
  reactEngine: ReActEngine;
  responsePipeline: ResponsePipelineProvider;
  emotionProvider: EmotionProvider;
  persistenceProvider: PersistenceProvider;
  limitPresenter: LimitPresenter;
  logger: TurnLogger;
}

export function officialDefaults(): OfficialVoiceAgentModules {
  return {
    configStore: new HostSessionConfigStore((sessionId, code) => {
      log.warn("official voice config warning", { sessionId, code });
    }),
    router: new DefaultTurnRouter(),
    contextProvider: new ListenAIContextProvider(),
    promptBuilder: new DefaultPromptBuilder(),
    modelResolver: new ConfigModelResolver(),
    knowledgeProvider: new ListenAIKnowledgeProvider(),
    memoryProvider: new ListenAIMemoryProvider(),
    historyProvider: new HostHistoryProvider(),
    toolProvider: new DefaultToolProvider(),
    aiuiProvider: new ListenAIAiuiProvider(),
    imageHandler: new DefaultImageTurnHandler(),
    reactEngine: new DefaultReActEngine(),
    responsePipeline: new DefaultResponsePipelineProvider(),
    emotionProvider: new DefaultEmotionProvider(),
    persistenceProvider: new ListenAIPersistenceProvider(),
    limitPresenter: new DefaultLimitPresenter(),
    logger: new StructuredTurnLogger(),
  };
}

export interface OfficialVoiceAgentOptions extends Partial<OfficialVoiceAgentModules> {
  systemPrompt?: string;
}

export function createOfficialVoiceAgent(
  overrides: OfficialVoiceAgentOptions = {},
): Agent {
  const { systemPrompt, ...moduleOverrides } = overrides;
  const modules = { ...officialDefaults(), ...moduleOverrides };
  const activeTurns = new Map<string, ActiveTurn>();
  return {
    onConnect(info): void {
      log.info("official voice agent connected", { sessionId: info.sessionId });
    },
    async onMessage(msg): Promise<void> {
      if (handleSessionEvent(modules, activeTurns, msg)) return;
      if (!msg.isLast) return;
      cancelActiveTurn(modules, activeTurns, msg.sessionId, "Superseded by a newer final ASR turn");
      const text = msg.content.tag === "text" ? boundedCurrentUserText(msg.content.val) : "";
      if (!text) {
        emitNLPFinish(msg.sessionId);
        return;
      }
      const config = modules.configStore.get(msg.sessionId);
      const image = readConfiguredImage(config?.nlu);
      const route = modules.router.route({ text, hasImage: Boolean(image) });
      if (route === "awake") {
        speakFixed(modules, msg.sessionId, randomWakeReply());
        return;
      }
      if (route === "exit") {
        speakFixed(modules, msg.sessionId, EXIT_REPLY, [buildExitFrame()]);
        return;
      }
      if (route === "clear") {
        Promise.resolve(modules.historyProvider.clear(msg.sessionId)).catch((error) => {
          log.warn("official voice history clear failed", {
            sessionId: msg.sessionId,
            errorCode: safeErrorCode(error),
          });
        });
        speakFixed(modules, msg.sessionId, CLEAR_REPLY);
        return;
      }
      if (route === "upload_log") {
        speakFixed(modules, msg.sessionId, UPLOAD_LOG_REPLY);
        return;
      }
      if (!config) {
        modules.responsePipeline.create(msg.sessionId).finish();
        log.warn("official voice turn has no valid configuration", { sessionId: msg.sessionId });
        return;
      }
      const lease = modules.configStore.acquire(msg.sessionId);
      if (!lease) {
        modules.responsePipeline.create(msg.sessionId).finish();
        log.warn("official voice turn could not acquire configuration", { sessionId: msg.sessionId });
        return;
      }
      log.info("current base url", { baseUrl: lease.config.baseUrl, sessionId: msg.sessionId });
      try {
        await runConversation(
          modules,
          activeTurns,
          msg,
          text,
          lease.config,
          readConfiguredImage(lease.config.nlu),
          systemPrompt,
        );
      } finally {
        lease.release();
      }
    },
    onInterrupt(sessionId): void {
      runBestEffortCleanup([
        () => cancelActiveTurn(modules, activeTurns, sessionId, "Device interrupted the active turn"),
        () => closeActiveTTSStream(),
        () => closeActiveTextStream(),
        () => log.info("official voice turn interrupted", { sessionId }),
      ]);
    },
    onDisconnect(sessionId): void {
      runBestEffortCleanup([
        () => cancelActiveTurn(modules, activeTurns, sessionId, "Session disconnected"),
        () => modules.toolProvider.cancelSession(sessionId, "Session disconnected"),
        () => modules.toolProvider.clearSession(sessionId),
        () => closeActiveTTSStream(),
        () => closeActiveTextStream(),
        () => modules.configStore.clear(sessionId),
        () => log.info("official voice agent disconnected", { sessionId }),
      ]);
    },
  };
}

function handleSessionEvent(
  modules: OfficialVoiceAgentModules,
  activeTurns: Map<string, ActiveTurn>,
  msg: DeviceMessage,
): boolean {
  if (msg.content.tag !== "event") return false;
  const event = msg.content.val;
  if (event.kind === "config") {
    try {
      modules.configStore.replace(msg.sessionId, JSON.parse(event.data) as unknown);
    } catch (error) {
      cancelActiveTurn(modules, activeTurns, msg.sessionId, "Invalid configuration replacement");
      modules.toolProvider.cancelSession(msg.sessionId, "Invalid configuration replacement");
      modules.toolProvider.clearSession(msg.sessionId);
      modules.configStore.clear(msg.sessionId);
      log.warn("invalid official voice config", safeErrorFields(error));
    }
  } else if (event.kind === "vpr_info") {
    host.kvSet(`listenai.voice.vpr.${msg.sessionId}`, event.data, 5);
  } else if (event.kind === "mcp_tool_result") {
    try {
      modules.toolProvider.resolveDeviceResult(
        msg.sessionId,
        JSON.parse(event.data) as unknown,
      );
    } catch {
      log.warn("invalid device tool result", { sessionId: msg.sessionId });
    }
  }
  return true;
}

function speakFixed(
  modules: OfficialVoiceAgentModules,
  sessionId: string,
  text: string,
  extraFrames: unknown[] = [],
): void {
  const response = modules.responsePipeline.create(sessionId);
  let completedWrite = false;
  try {
    response.start();
    response.write(text);
    completedWrite = true;
  } catch (error) {
    log.warn("official fixed response failed", {
      sessionId,
      ...safeErrorFields(error),
    });
  } finally {
    try {
      response.finish(completedWrite ? extraFrames : []);
    } catch (error) {
      log.warn("official fixed response finish failed", {
        sessionId,
        ...safeErrorFields(error),
      });
    }
  }
}

interface ActiveTurn {
  context: VoiceTurnContext;
  cancellation: CancellationTokenSource;
  response: ResponsePipeline;
}

type PreparationResult<T> =
  | { ok: true; value: T }
  | { ok: false; error: unknown };

type TimedPreparationResult<T> = PreparationResult<T> & { durationMs: number };

function settlePreparation<T>(promise: Promise<T>): Promise<PreparationResult<T>> {
  return promise.then(
    (value) => ({ ok: true, value }),
    (error: unknown) => ({ ok: false, error }),
  );
}

async function settleTimedPreparation<T>(start: () => Promise<T>): Promise<TimedPreparationResult<T>> {
  const startedAt = Date.now();
  try {
    return { ok: true, value: await start(), durationMs: Date.now() - startedAt };
  } catch (error) {
    return { ok: false, error, durationMs: Date.now() - startedAt };
  }
}

const TOOL_CATALOG_AVAILABILITY_CODES = new Set([
  "AGENT_TOOL_CATALOG_UNAVAILABLE",
  "AGENT_UPSTREAM_ERROR",
  "AGENT_UPSTREAM_TIMEOUT",
  "upstream-error",
  "timeout-io",
  "quota-http",
]);

function isToolCatalogAvailabilityError(error: unknown): boolean {
  const normalized = asAgentError(error);
  return normalized.retryable && TOOL_CATALOG_AVAILABILITY_CODES.has(normalized.code);
}

async function runConversation(
  modules: OfficialVoiceAgentModules,
  activeTurns: Map<string, ActiveTurn>,
  msg: DeviceMessage,
  userText: string,
  config: NormalizedSessionConfig,
  image: string,
  systemPrompt?: string,
): Promise<void> {
  const cancellation = new CancellationTokenSource();
  const turnId = uuidV4();
  const context: VoiceTurnContext = {
    sessionId: msg.sessionId,
    turnId,
    requestId: correlationId("request"),
    deviceId: msg.deviceId,
    productId: msg.productId,
    userText,
    voiceProfileId: messageParameter(msg, "vpr_feature_id"),
    vprInfo: consumeVPRInfo(msg.sessionId),
    memoryPolicy: disabledRuntimeMemoryPolicy(),
    dsaPolicy: disabledServerDsaPolicy(),
    config,
    cancellation: cancellation.token,
  };
  const response = modules.responsePipeline.create(msg.sessionId);
  const active: ActiveTurn = { context, cancellation, response };
  const startedAt = Date.now();
  let firstFrameLogged = false;
  let preparedTools: PreparedTools | null = null;
  let emotionTask: Promise<void> | undefined;
  let requestHistoryMessages: AgentChatMessage[] = [];
  let cameraImage = "";
  try {
    activeTurns.set(msg.sessionId, active);
    response.start();
    safeTurnLog("started", context, () => modules.logger.started(context));
    if (image) {
      await runImageConversation(modules, context, response, image, startedAt);
      return;
    }
    const contextPrepareStartedAt = Date.now();
    const prepared = await modules.contextProvider.prepare(context);
    const contextPrepareDurationMs = Date.now() - contextPrepareStartedAt;
    safeTurnLog("phase", context, () => modules.logger.phase?.(
      context,
      "runtime_context_prepared",
      Date.now() - startedAt,
      { durationMs: contextPrepareDurationMs },
    ));
    context.memoryPolicy = parseRuntimeMemoryPolicy(prepared.product_config);
    context.dsaPolicy = parseServerDsaPolicy(prepared.product_config);
    for (const warning of prepared.warnings) {
      safeTurnLog("warning", context, () => modules.logger.warning(context, warning.code, warning.section));
    }
    // Start event-driven Runtime requests before the synchronous history Host
    // call so their network work can progress while history is being loaded.
    const dependencyPrepareStartedAt = Date.now();
    const [memoryResult, toolsResult, aiuiResult, knowledgeResult, historyResult] = await Promise.all([
      settlePreparation(modules.memoryProvider.recall(context)),
      settlePreparation(modules.toolProvider.prepare(context, {
        dsaPolicy: context.dsaPolicy,
      }).catch((error) => {
        // A debug-emotion request is deliberately independent of Runtime's
        // device-tool authorization. Continue with an empty catalog so the
        // emotion provider can emit its fixed xiaoling frame directly.
        if (!isDebugEmotionRequest(config) && !isToolCatalogAvailabilityError(error)) throw error;
        safeTurnLog(
          "warning",
          context,
          () => modules.logger.warning(context, "tools.catalog_unavailable", "tools"),
        );
        log.warn("tool catalog unavailable; continuing without tools", {
          turnId: context.turnId,
          ...safeErrorFields(error),
        });
        return emptyPreparedTools();
      })),
      settlePreparation(modules.aiuiProvider.resolve(context, prepared.location?.city)),
      settlePreparation(modules.knowledgeProvider.query(context)),
      settleTimedPreparation(() => modules.historyProvider.load(context)),
    ]);
    safeTurnLog("phase", context, () => modules.logger.phase?.(
      context,
      "runtime_dependencies_prepared",
      Date.now() - startedAt,
      {
        durationMs: Date.now() - dependencyPrepareStartedAt,
        memoryOk: memoryResult.ok,
        toolsOk: toolsResult.ok,
        aiuiOk: aiuiResult.ok,
        knowledgeOk: knowledgeResult.ok,
        historyOk: historyResult.ok,
      },
    ));
    if (!memoryResult.ok) {
      if (toolsResult.ok) safeCloseTools(toolsResult.value, context);
      throw memoryResult.error;
    }
    if (!toolsResult.ok) throw toolsResult.error;
    if (!aiuiResult.ok) {
      safeCloseTools(toolsResult.value, context);
      throw aiuiResult.error;
    }
    if (!knowledgeResult.ok) {
      safeCloseTools(toolsResult.value, context);
      throw knowledgeResult.error;
    }
    const memory = memoryResult.value;
    const tools = toolsResult.value;
    const aiui = aiuiResult.value;
    const knowledge = knowledgeResult.value;
    preparedTools = tools;
    for (const warning of memory.warnings) {
      safeTurnLog("warning", context, () => modules.logger.warning(context, warning, "memory"));
    }
    for (const warning of tools.warnings) {
      safeTurnLog("warning", context, () => modules.logger.warning(context, warning, "tools"));
    }
    if (aiui.warning) {
      safeTurnLog("warning", context, () => modules.logger.warning(context, aiui.warning!, "aiui"));
    }
    response.emitFrames(aiui.frames);

    for (const warning of knowledge.warnings) {
      safeTurnLog("warning", context, () => modules.logger.warning(context, warning, "knowledge"));
    }

    if (aiui.handled) {
      if (aiui.answer) {
        logFirstFrame(modules, context, startedAt, () => { firstFrameLogged = true; });
        response.write(aiui.answer);
      }
      logReply(modules, context, response.finalAnswer || aiui.answer || "", {
        status: "COMPLETED",
        stopReason: "completed",
      }, startedAt);
      await persistCompleted(modules, context, response, startedAt, requestHistoryMessages);
      return;
    }
    response.emitFrames(knowledge.frames);

    if (knowledge.faqDirectReply && knowledge.promptContent) {
      logFirstFrame(modules, context, startedAt, () => { firstFrameLogged = true; });
      response.write(knowledge.promptContent);
      logReply(modules, context, response.finalAnswer, {
        status: "COMPLETED",
        stopReason: "completed",
      }, startedAt);
      await persistCompleted(modules, context, response, startedAt, requestHistoryMessages);
      return;
    }

    if (historyResult.ok) {
      requestHistoryMessages = historyResult.value;
      safeTurnLog("phase", context, () => modules.logger.phase?.(
        context,
        "history_loaded",
        Date.now() - startedAt,
        { durationMs: historyResult.durationMs },
      ));
    } else {
      safeTurnLog("phase", context, () => modules.logger.phase?.(
        context,
        "history_load_failed",
        Date.now() - startedAt,
        { durationMs: historyResult.durationMs },
      ));
      safeTurnLog("warning", context, () => modules.logger.warning(context, "history.unavailable", "history"));
      log.warn("official voice history load failed", {
        turnId: context.turnId,
        errorCode: safeErrorCode(historyResult.error),
      });
    }

    const resolved = modules.modelResolver.resolve(context);
    // Match the source flow: emotion classification runs beside the main
    // response and settles before the turn is persisted and finished.
    emotionTask = modules.emotionProvider.run(
      context,
      tools.catalog,
      modules.modelResolver,
    );
    const preparedPrompt = promptInput(
      context,
      prepared,
      memory.longMemory,
      memory.preferences,
      knowledge.promptContent,
      tools.catalog,
      requestHistoryMessages,
      systemPrompt,
    );
    const messages = modules.promptBuilder.build(preparedPrompt);
    safeTurnLog("phase", context, () => modules.logger.phase?.(
      context,
      "main_model_starting",
      Date.now() - startedAt,
      { messageCount: messages.length, toolCount: tools.registry.definitions().length },
    ));
    const result = await modules.reactEngine.run({
      turnId: context.turnId,
      modelName: resolved.modelName,
      messages,
      historyMessageCount: preparedPrompt.history.length,
      model: resolved.model,
      fallback: resolved.fallback,
      tools: tools.registry,
      maxSteps: context.config.runtime.react.maxSteps,
      maxToolCalls: context.config.runtime.react.maxToolCalls,
      userText: context.userText,
      toolChoice: tools.toolChoice,
      temperature: context.config.runtime.model.temperature,
      maxTokens: context.config.runtime.model.maxTokens,
      timeoutMs: context.config.runtime.model.timeoutMs,
      cancellation: context.cancellation,
      requestContext: {
        sessionId: context.sessionId,
        appId: context.config.businessAppId,
        requestId: context.requestId,
        cancellation: context.cancellation,
      },
    }, {
      onEvent: (event) => {
        if (event.type === "output.delta" && !firstFrameLogged) {
          logFirstFrame(modules, context, startedAt, () => { firstFrameLogged = true; });
        }
        safeTurnLog("react_event", context, () => modules.logger.reactEvent?.(
          context,
          event,
          Date.now() - startedAt,
        ));
        response.handleEvent(event);
        if (event.type === "tool.completed" && event.call.name === "take_photo" && !cameraImage) {
          cameraImage = mapToolImageArtifacts(event.call.name, event.result)
            .map(imageArtifactSource)
            .find(Boolean) ?? "";
        }
      },
    });
    if (cameraImage) {
      await emotionTask;
      await runImageConversation(modules, context, response, cameraImage, startedAt, result);
      return;
    }
    response.flush();
    await emotionTask;
    logReply(modules, context, response.finalAnswer, {
      status: result.status,
      stopReason: result.stopReason,
    }, startedAt);
    await persistSafely(modules, {
      context,
      finalAnswer: response.finalAnswer,
      runResult: result,
      status: "completed",
      stopReason: response.endSession
        ? "end_session"
        : response.ignoreSession
          ? "ignore_session"
          : result.stopReason,
      historyPolicy: response.ignoreSession ? "skip" : "store",
      elapsedMs: Date.now() - startedAt,
      imageArtifacts: response.imageArtifacts,
      requestHistoryMessages,
      outputMeta: response.outputMeta,
    });
    safeTurnLog(
      "completed",
      context,
      () => modules.logger.completed(context, result.status, Date.now() - startedAt),
    );
  } catch (error) {
    if (emotionTask) await emotionTask.catch(() => undefined);
    const normalized = asAgentError(error);
    let completionError: PersistenceInput["error"];
    if (normalized.code === "AGENT_MODEL_CONTEXT_TOO_LARGE") {
      completionError = {
        code: "AGENT_MODEL_CONTEXT_TOO_LARGE",
        message: "Model context remains too large",
      };
    }
    safeResponseCall("discard_pending", context, () => response.discardPending());
    const stop = mapAgentErrorStop(normalized, response.hasActivity);
    const limit = await presentLimitSafely(modules, normalized, context);
    if (limit) {
      const limitText = stripHTMLTags(limit.message);
      if (limitText) safeResponseCall("write_limit", context, () => response.write(limitText));
    }
    safeResponseCall("flush", context, () => response.flush());
    await persistSafely(modules, {
      context,
      finalAnswer: response.finalAnswer,
      status: stop.status,
      stopReason: stop.reason,
      ...(completionError ? { error: completionError } : {}),
      historyPolicy: stop.historyPolicy,
      elapsedMs: Date.now() - startedAt,
      imageArtifacts: response.imageArtifacts,
      requestHistoryMessages,
      outputMeta: response.outputMeta,
    });
    safeTurnLog(
      "failed",
      context,
      () => modules.logger.failed(context, normalized.code, Date.now() - startedAt),
    );
  } finally {
    if (activeTurns.get(msg.sessionId) === active) activeTurns.delete(msg.sessionId);
    if (preparedTools) safeCloseTools(preparedTools, context);
    safeResponseCall("finish", context, () => response.finish());
  }
}

async function runImageConversation(
  modules: OfficialVoiceAgentModules,
  context: VoiceTurnContext,
  response: ResponsePipeline,
  image: string,
  startedAt: number,
  runResult?: RunResult,
): Promise<void> {
  let firstFrameLogged = false;
  const imageResult = await modules.imageHandler.run(
    context,
    image,
    modules.modelResolver,
    (delta) => {
      if (delta && !firstFrameLogged) {
        logFirstFrame(modules, context, startedAt, () => { firstFrameLogged = true; });
      }
      response.write(delta);
    },
  );
  response.flush();
  const finalAnswer = response.finalAnswer || imageResult.answer;
  logReply(modules, context, finalAnswer, {
    status: "COMPLETED",
    stopReason: "completed",
  }, startedAt);
  await persistSafely(modules, {
    context,
    finalAnswer,
    ...(runResult
      ? { runResult }
      : {
        historyMessages: [
          ...imageResult.messages,
          { role: "assistant", content: finalAnswer },
        ],
      }),
    status: "completed",
    stopReason: response.endSession ? "end_session" : "completed",
    historyPolicy: response.ignoreSession ? "skip" : "store",
    elapsedMs: Date.now() - startedAt,
    imageArtifacts: response.imageArtifacts,
    outputMeta: response.outputMeta,
  });
  safeTurnLog(
    "completed",
    context,
    () => modules.logger.completed(context, "COMPLETED", Date.now() - startedAt),
  );
}

function logFirstFrame(
  modules: OfficialVoiceAgentModules,
  context: VoiceTurnContext,
  startedAt: number,
  markLogged: () => void,
): void {
  markLogged();
  safeTurnLog("first_frame", context, () => modules.logger.firstFrame?.(
    context,
    Date.now() - startedAt,
  ));
}

function logReply(
  modules: OfficialVoiceAgentModules,
  context: VoiceTurnContext,
  answer: string,
  result: Pick<import("@listenai/agent-sdk").RunResult, "status" | "stopReason">,
  startedAt: number,
): void {
  safeTurnLog("final_reply", context, () => modules.logger.reply?.(
    context,
    answer,
    result,
    Date.now() - startedAt,
  ));
}

async function persistCompleted(
  modules: OfficialVoiceAgentModules,
  context: VoiceTurnContext,
  response: ResponsePipeline,
  startedAt: number,
  requestHistoryMessages: AgentChatMessage[] = [],
): Promise<void> {
  response.flush();
  await persistSafely(modules, {
    context,
    finalAnswer: response.finalAnswer,
    status: "completed",
    stopReason: response.endSession ? "end_session" : "completed",
    historyPolicy: response.ignoreSession ? "skip" : "store",
    elapsedMs: Date.now() - startedAt,
    imageArtifacts: response.imageArtifacts,
    requestHistoryMessages,
    outputMeta: response.outputMeta,
  });
  safeTurnLog(
    "completed",
    context,
    () => modules.logger.completed(context, "COMPLETED", Date.now() - startedAt),
  );
}

async function persistSafely(
  modules: OfficialVoiceAgentModules,
  input: Parameters<PersistenceProvider["persist"]>[0],
): Promise<void> {
  try {
    await modules.persistenceProvider.persist({
      ...input,
      historyProvider: input.historyProvider ?? modules.historyProvider,
    });
  } catch (error) {
    log.warn("official voice turn persistence failed", {
      turnId: input.context.turnId,
      errorCode: safeErrorCode(error),
    });
  }
}

async function presentLimitSafely(
  modules: OfficialVoiceAgentModules,
  error: ReturnType<typeof asAgentError>,
  context: VoiceTurnContext,
): ReturnType<LimitPresenter["present"]> {
  try {
    return await modules.limitPresenter.present(error, context);
  } catch (presentError) {
    log.warn("official voice quota presentation failed", {
      turnId: context.turnId,
      errorCode: safeErrorCode(presentError),
    });
    return null;
  }
}

function safeTurnLog(
  event: string,
  context: VoiceTurnContext,
  write: () => void,
): void {
  try {
    write();
  } catch (error) {
    log.warn("official voice structured logger failed", {
      turnId: context.turnId,
      event,
      errorCode: safeErrorCode(error),
    });
  }
}

function safeResponseCall(
  operation: string,
  context: VoiceTurnContext,
  call: () => void,
): void {
  try {
    call();
  } catch (error) {
    log.warn("official voice response operation failed", {
      turnId: context.turnId,
      operation,
      errorCode: safeErrorCode(error),
    });
  }
}

function safeCloseTools(tools: PreparedTools, context: VoiceTurnContext): void {
  try {
    tools.close();
  } catch (error) {
    log.warn("official voice tool cleanup failed", {
      turnId: context.turnId,
      errorCode: safeErrorCode(error),
    });
  }
}

function promptInput(
  context: VoiceTurnContext,
  prepared: Awaited<ReturnType<ContextProvider["prepare"]>>,
  longMemory: string,
  preferences: Array<{ text?: string }>,
  knowledge: string,
  catalog: PreparedTools["catalog"],
  historyMessages: Awaited<ReturnType<HistoryProvider["load"]>>,
  systemPrompt?: string,
) {
  const role = isRecord(prepared.role) ? prepared.role : {};
  const profile = isRecord(prepared.voice_profile) ? prepared.voice_profile : {};
  const nlu = mergePreparedNluContext(
    isRecord(prepared.product_config) ? prepared.product_config : {},
    isRecord(prepared.device_config) ? prepared.device_config : {},
    context.config.nlu,
  );
  const loadedHistory = historyMessages.map(toHostHistoryMessage);
  const selectedHistory = selectRecentHistory(loadedHistory);
  const multimodalMessageCount = selectedHistory.filter(
    (message) => Array.isArray(message.content),
  ).length;
  const history = projectHistoryForTextModel(selectedHistory).slice(-MAX_HISTORY_FETCH_MESSAGES);
  log.info("official voice history prepared", {
    turnId: context.turnId,
    loadedMessageCount: loadedHistory.length,
    selectedMessageCount: history.length,
    projectedMultimodalMessageCount: multimodalMessageCount,
    toolCallMessageCount: history.filter((message) => message.toolCalls?.length).length,
    toolResultMessageCount: history.filter((message) => message.role === "tool").length,
  });
  return {
    explicitSystemPrompt: systemPrompt,
    configuredSystemPrompt: stringField(nlu, "agent_system_prompt"),
    platformSystemPrompt: stringField(prepared.product_config, "default_agent_system_prompt"),
    persona: stringField(role, "persona") || stringField(nlu, "persona"),
    portrait: stringField(role, "portrait") || stringField(nlu, "portrait"),
    userName: stringField(profile, "name"),
    city: prepared.location?.city,
    memory: formatMemory(longMemory, preferences),
    knowledge,
    dsaSystemPrompt: context.dsaPolicy.enabled ? context.dsaPolicy.systemPrompt : undefined,
    emotion: emotionToolDescription(catalog),
    wakeWord: prepared.wakeup_word,
    history,
    userText: context.userText,
  };
}

function toHostHistoryMessage(message: AgentChatMessage): HostChatMessage {
  const stored = message as AgentChatMessage & { meta?: Record<string, unknown> | null };
  const meta: Record<string, unknown> = { ...(stored.meta ?? {}) };
  if (message.name && typeof meta.name !== "string") meta.name = message.name;
  return {
    role: message.role,
    content: message.content,
    toolCallId: message.toolCallId ?? null,
    ...(message.toolCalls?.length ? { toolCalls: message.toolCalls } : {}),
    ...(Object.keys(meta).length > 0 ? { meta } : {}),
  };
}

function emotionToolDescription(catalog: PreparedTools["catalog"]): string {
  for (const capability of catalog.device_capabilities) {
    if (capability.original_name !== "ls.built_in.set_emotion") continue;
    const description = capability.definition.function.description;
    if (typeof description === "string") return description.slice(0, 4_000);
  }
  const fallback = catalog.tools.find((tool) => (
    tool.function.name === "ls.built_in.set_emotion" || tool.function.name === "set_emotion"
  ));
  return fallback?.function.description?.slice(0, 4_000) ?? "";
}

function consumeVPRInfo(sessionId: string): Record<string, unknown> | undefined {
  const key = `listenai.voice.vpr.${sessionId}`;
  const raw = host.kvGet(key);
  if (!raw) return undefined;
  host.kvSet(key, "", 1);
  if (raw.length > 8192) return undefined;
  try {
    const value = JSON.parse(raw) as unknown;
    return isRecord(value) ? value : undefined;
  } catch {
    return undefined;
  }
}

function formatMemory(longMemory: string, preferences: Array<{ text?: string }>): string {
  const preferenceText = preferences
    .map((preference) => typeof preference.text === "string" ? preference.text : "")
    .filter(Boolean)
    .join("\n");
  return [longMemory, preferenceText].filter(Boolean).join("\n\n");
}

function cancelActiveTurn(
  modules: OfficialVoiceAgentModules,
  activeTurns: Map<string, ActiveTurn>,
  sessionId: string,
  reason: string,
): void {
  const active = activeTurns.get(sessionId);
  if (!active) return;
  runBestEffortCleanup([
    () => active.response.abort(false),
    () => active.cancellation.cancel(reason),
    () => modules.reactEngine.cancel(active.context.turnId, reason),
    () => modules.toolProvider.cancelSession(sessionId, reason),
  ]);
}

function runBestEffortCleanup(steps: Array<() => void>): void {
  let failed = false;
  let firstError: unknown;
  for (const step of steps) {
    try {
      step();
    } catch (error) {
      if (!failed) {
        failed = true;
        firstError = error;
      }
    }
  }
  if (failed) throw firstError;
}

function messageParameter(msg: DeviceMessage, name: string): string | undefined {
  const pair = msg.params.find(([key]) => key === name);
  return pair?.[1] || undefined;
}

function stringField(value: unknown, key: string): string {
  return isRecord(value) && typeof value[key] === "string" ? String(value[key]) : "";
}

function correlationId(prefix: string): string {
  const random = Math.floor(Math.random() * 0x7fffffff).toString(36);
  return `${prefix}:${Date.now().toString(36)}:${random}`;
}

function emptyPreparedTools(): PreparedTools {
  return {
    registry: new ToolRegistry(),
    catalog: {
      tools: [],
      tool_bindings: {},
      device_capabilities: [],
      etag: "",
    },
    toolChoice: "auto",
    warnings: ["tools.catalog_unavailable"],
    close(): void {},
  };
}

function isDebugEmotionRequest(config: NormalizedSessionConfig): boolean {
  return config.features?.includes(DEBUG_EMOTION_FEATURE) === true;
}

function randomWakeReply(): string {
  return WAKE_REPLIES[Math.floor(Math.random() * WAKE_REPLIES.length)] ?? WAKE_REPLIES[0];
}

function readConfiguredImage(nlu: Record<string, unknown> | undefined): string {
  const custom = nlu && isRecord(nlu.custom) ? nlu.custom : undefined;
  const image = custom && typeof custom.image === "string" ? custom.image : "";
  return image.startsWith("/9j/") ? `data:image/jpeg;base64,${image}` : image;
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}
