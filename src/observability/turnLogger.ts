import { log, type AgentEvent, type AgentToolResult, type ModelRequest, type RunResult } from "@listenai/agent-sdk";
import type { VoiceTurnContext } from "../types";
import { safeErrorFields, safeLogUrl } from "../errors/safeLogging";
import { truncateUtf8, utf8ByteLength } from "../text/utf8Budget";

export interface TurnLogger {
  started(context: VoiceTurnContext): void;
  phase?(
    context: VoiceTurnContext,
    phase: string,
    elapsedMs: number,
    details?: Record<string, unknown>,
  ): void;
  warning(context: VoiceTurnContext, code: string, section: string): void;
  completed(context: VoiceTurnContext, outcome: string, elapsedMs: number): void;
  failed(context: VoiceTurnContext, code: string, elapsedMs: number): void;
  firstFrame?(context: VoiceTurnContext, elapsedMs: number): void;
  reactEvent?(context: VoiceTurnContext, event: AgentEvent, elapsedMs: number): void;
  reply?(
    context: VoiceTurnContext,
    answer: string,
    result: Pick<RunResult, "status" | "stopReason">,
    elapsedMs: number,
  ): void;
}

export class StructuredTurnLogger implements TurnLogger {
  private readonly modelStarts = new Map<string, number>();
  private readonly toolStarts = new Map<string, number>();
  private readonly firstFrames = new Map<string, number>();

  started(context: VoiceTurnContext): void {
    log.info("official voice turn started", { ...fields(context), event: "turn.started" });
  }

  phase(
    context: VoiceTurnContext,
    phase: string,
    elapsedMs: number,
    details: Record<string, unknown> = {},
  ): void {
    log.info("official voice turn phase", {
      ...fields(context),
      event: "turn.phase",
      phase,
      elapsedMs,
      ...details,
    });
  }

  warning(context: VoiceTurnContext, code: string, section: string): void {
    log.warn("official voice turn degraded", { ...fields(context), event: "turn.degraded", code, section });
  }

  completed(context: VoiceTurnContext, outcome: string, elapsedMs: number): void {
    log.info("official voice turn completed", { ...fields(context), event: "turn.completed", outcome, elapsedMs });
  }

  failed(context: VoiceTurnContext, code: string, elapsedMs: number): void {
    log.warn("official voice turn failed", { ...fields(context), event: "turn.failed", code, elapsedMs });
  }

  firstFrame(context: VoiceTurnContext, elapsedMs: number): void {
    this.firstFrames.set(context.turnId, elapsedMs);
    log.info("official voice first frame", { ...fields(context), event: "response.first_frame", firstFrameMs: elapsedMs });
  }

  reactEvent(context: VoiceTurnContext, event: AgentEvent, elapsedMs: number): void {
    const base = { ...fields(context), elapsedMs };
    switch (event.type) {
      case "model.started":
        this.modelStarts.set(eventKey(context, event.modelCallId), elapsedMs);
        log.info("official voice react model started", {
          ...base,
          event: "model.started",
          modelCallId: event.modelCallId,
          model: event.model,
          ...modelRequestSummaryFields(event.request),
        });
        // Full prompt sanitization and JSON sizing can be expensive in Goja,
        // especially after image/tool history is present. Keep model startup
        // on the critical path lightweight and emit the detailed trace later.
        deferHostLog(() => {
          log.info("official voice react model request", {
            ...base,
            event: "model.request",
            ...modelRequestFields(event.requestId, event.request),
          });
        });
        return;
      case "model.completed":
        const modelKey = eventKey(context, event.modelCallId);
        log.info("official voice react model completed", {
          ...base,
          event: "model.completed",
          modelCallId: event.modelCallId,
          finishReason: event.finishReason,
          durationMs: elapsedSince(this.modelStarts.get(modelKey), elapsedMs),
        });
        this.modelStarts.delete(modelKey);
        return;
      case "tool.started":
        this.toolStarts.set(eventKey(context, event.call.id), elapsedMs);
        log.info("official voice react tool started", {
          ...base,
          event: "tool.started",
          toolCallId: event.call.id,
          toolName: event.call.name,
          argumentKeys: Object.keys(event.call.parsedArguments),
          argumentBytes: utf8ByteLength(JSON.stringify(event.call.parsedArguments)),
          ...toolArgumentsLogFields(event.call.parsedArguments),
        });
        return;
      case "tool.completed":
        const completedToolKey = eventKey(context, event.call.id);
        log.info("official voice react tool completed", {
          ...base,
          event: "tool.completed",
          toolCallId: event.call.id,
          toolName: event.call.name,
          isError: event.result.isError,
          contentCount: event.result.content.length,
          artifactTypes: event.result.artifacts.map((artifact) => artifact.type),
          ...toolResultLogFields(event.result),
          durationMs: elapsedSince(this.toolStarts.get(completedToolKey), elapsedMs),
        });
        this.toolStarts.delete(completedToolKey);
        return;
      case "tool.failed":
        const failedToolKey = eventKey(context, event.call.id);
        log.warn("official voice react tool failed", {
          ...base,
          event: "tool.failed",
          toolCallId: event.call.id,
          toolName: event.call.name,
          ...safeErrorFields(event.error),
          durationMs: elapsedSince(this.toolStarts.get(failedToolKey), elapsedMs),
        });
        this.toolStarts.delete(failedToolKey);
        return;
      case "usage":
        log.info("official voice react model usage", {
          ...base,
          event: "model.usage",
          modelCallId: event.modelCallId,
          ...event.usage,
        });
        return;
      case "run.completed":
        log.info("official voice react completed", {
          ...base,
          event: "react.completed",
          status: event.result.status,
          stopReason: event.result.stopReason,
          modelSteps: event.result.modelSteps,
          toolCalls: event.result.toolCalls,
          artifactCount: event.result.artifacts.length,
        });
        this.clearTurn(context.turnId, false);
        return;
      case "run.failed":
        log.warn("official voice react failed", {
          ...base,
          event: "react.failed",
          ...safeErrorFields(event.error),
        });
        this.clearTurn(context.turnId);
        return;
      case "output.delta":
        // Output is logged as a single first-frame event and as a final reply
        // summary; logging every token would overwhelm production logs.
        return;
    }
  }

  private clearTurn(turnId: string, clearFirstFrame = true): void {
    const prefix = `${turnId}:`;
    for (const key of this.modelStarts.keys()) {
      if (key.startsWith(prefix)) this.modelStarts.delete(key);
    }
    for (const key of this.toolStarts.keys()) {
      if (key.startsWith(prefix)) this.toolStarts.delete(key);
    }
    if (clearFirstFrame) this.firstFrames.delete(turnId);
  }

  reply(
    context: VoiceTurnContext,
    answer: string,
    result: Pick<RunResult, "status" | "stopReason">,
    elapsedMs: number,
  ): void {
    try {
      log.info("official voice final reply", {
        ...fields(context),
        event: "response.final",
        ...result,
        elapsedMs,
        ...(this.firstFrames.has(context.turnId)
          ? { firstFrameMs: this.firstFrames.get(context.turnId) }
          : {}),
        ...finalAnswerLogFields(answer),
      });
    } finally {
      this.firstFrames.delete(context.turnId);
    }
  }
}

function eventKey(context: VoiceTurnContext, id: string): string {
  return `${context.turnId}:${id}`;
}

function elapsedSince(startedAt: number | undefined, elapsedMs: number): number {
  return startedAt === undefined ? elapsedMs : Math.max(0, elapsedMs - startedAt);
}

const MAX_MODEL_MESSAGES_LOG_BYTES = 96 << 10;
const MAX_MODEL_TOOLS_LOG_BYTES = 64 << 10;
const MAX_TOOL_ARGUMENTS_LOG_BYTES = 16 << 10;
const MAX_TOOL_RESULT_LOG_BYTES = 8 << 10;
const MAX_FINAL_ANSWER_LOG_BYTES = 128 << 10;
const SENSITIVE_LOG_KEY = /(authorization|cookie|token|api[_-]?key|secret|password|credential)/i;

export function toolResultLogFields(result: AgentToolResult): Record<string, unknown> {
  const content = boundedLogValue(result.content, MAX_TOOL_RESULT_LOG_BYTES);
  return {
    resultContent: content.value,
    resultContentBytes: content.bytes,
    resultContentTruncated: content.truncated,
  };
}

export function toolArgumentsLogFields(argumentsValue: Record<string, unknown>): Record<string, unknown> {
  const argumentsLog = boundedLogValue(argumentsValue, MAX_TOOL_ARGUMENTS_LOG_BYTES);
  return {
    toolArguments: argumentsLog.value,
    toolArgumentsBytes: argumentsLog.bytes,
    toolArgumentsTruncated: argumentsLog.truncated,
  };
}

export function finalAnswerLogFields(answer: string): Record<string, unknown> {
  const safeAnswer = safeLogUrl(answer);
  const answerLog = boundedLogValue(safeAnswer, MAX_FINAL_ANSWER_LOG_BYTES);
  return {
    answer: answerLog.value,
    answerBytes: utf8ByteLength(answer),
    answerTruncated: answerLog.truncated,
    answerPreview: truncateUtf8(safeAnswer.replace(/\s+/g, " ").trim(), 256),
  };
}

export function safeModelRequestLog(
  message: string,
  context: VoiceTurnContext,
  requestId: string,
  request: ModelRequest,
  extra: Record<string, unknown> = {},
): void {
  deferHostLog(() => {
    try {
      log.info(message, {
        ...fields(context),
        event: "model.request",
        ...extra,
        ...modelRequestFields(requestId, request),
      });
    } catch {
      // Logging must never change model execution in lightweight hosts.
    }
  });
}

export function modelRequestSummaryFields(request: ModelRequest): Record<string, unknown> {
  const tools = request.tools ?? [];
  return {
    messageCount: request.messages.length,
    toolCount: tools.length,
    toolNames: tools.map((tool) => tool.function.name),
  };
}

function deferHostLog(callback: () => void): void {
  const run = (): void => {
    try {
      callback();
    } catch {
      // Observability must never change model execution in lightweight hosts.
    }
  };
  try {
    if (typeof host !== "undefined" && typeof host.timerStart === "function") {
      host.timerStart(1, run);
      return;
    }
  } catch {
    // Fall through to the inline fallback for lightweight test hosts.
  }
  // Lightweight unit-test hosts do not always expose timers. Run inline in
  // that environment so a later test/session cannot observe a stale log.
  run();
}

export function modelRequestFields(requestId: string, request: ModelRequest): Record<string, unknown> {
  const messages = boundedLogValue(request.messages, MAX_MODEL_MESSAGES_LOG_BYTES);
  const tools = boundedLogValue(request.tools ?? [], MAX_MODEL_TOOLS_LOG_BYTES);
  return {
    requestId,
    modelCallId: request.modelCallId,
    modelRequest: {
      modelCallId: request.modelCallId,
      purpose: request.purpose,
      model: request.model,
      messages: messages.value,
      messagesBytes: messages.bytes,
      messagesTruncated: messages.truncated,
      tools: tools.value,
      toolsBytes: tools.bytes,
      toolsTruncated: tools.truncated,
      toolNames: (request.tools ?? []).map((tool) => tool.function.name),
      toolChoice: request.toolChoice,
      temperature: request.temperature,
      maxTokens: request.maxTokens,
      firstFrameTimeoutMs: request.firstFrameTimeoutMs,
      idleTimeoutMs: request.idleTimeoutMs,
      totalTimeoutMs: request.totalTimeoutMs,
      timeoutMs: request.timeoutMs,
    },
  };
}

function boundedLogValue(value: unknown, maxBytes: number): {
  value: unknown;
  bytes: number;
  truncated: boolean;
} {
  const sanitized = sanitizeLogValue(value);
  let serialized: string;
  try {
    serialized = JSON.stringify(sanitized);
  } catch {
    return { value: "[UNSERIALIZABLE]", bytes: 0, truncated: true };
  }
  const bytes = utf8ByteLength(serialized);
  if (bytes <= maxBytes) return { value: sanitized, bytes, truncated: false };
  return {
    value: {
      truncated: true,
      preview: truncateUtf8(serialized, maxBytes),
    },
    bytes,
    truncated: true,
  };
}

function sanitizeLogValue(value: unknown, depth = 0): unknown {
  if (depth > 12) return "[DEPTH_LIMIT]";
  if (Array.isArray(value)) return value.map((item) => sanitizeLogValue(item, depth + 1));
  if (typeof value === "string") return sanitizeURLQuery(value);
  if (typeof value !== "object" || value === null) return value;
  const output: Record<string, unknown> = {};
  for (const [key, item] of Object.entries(value)) {
    output[key] = SENSITIVE_LOG_KEY.test(key)
      ? "[REDACTED]"
      : sanitizeLogValue(item, depth + 1);
  }
  return output;
}

function sanitizeURLQuery(value: string): string {
  return safeLogUrl(value);
}

function fields(context: VoiceTurnContext): Record<string, unknown> {
  return {
    sessionId: context.sessionId,
    turnId: context.turnId,
    requestId: context.requestId,
    productId: context.productId,
    deviceId: context.deviceId,
  };
}
