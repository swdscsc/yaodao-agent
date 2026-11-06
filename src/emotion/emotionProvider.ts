import {
  emitRaw,
  log,
  type ModelRequest,
  type ToolCatalogResponse,
} from "@listenai/agent-sdk";
import type { ModelResolver } from "../model/configModelResolver";
import type { VoiceTurnContext } from "../types";
import { buildToolCallFrame } from "../tools/deviceFrameAdapter";
import { safeErrorFields } from "../errors/safeLogging";
import { safeModelRequestLog } from "../observability/turnLogger";

const EMOTION_TOOL = "ls.built_in.set_emotion";
const EMOTION_TOOL_ALIAS = "set_emotion";
// Integration's Agent Runtime model catalog currently exposes DeepSeek only.
// Keep the emotion policy fixed while using the server-allowlisted public ID.
const EMOTION_MODEL = "deepseek-v4-flash";
export const DEBUG_EMOTION_FEATURE = "debug-emotion";
export const DEFAULT_EMOTION_TOOL_DESCRIPTION =
  "neutral, happy, laughing, funny, sad, angry, crying, loving, embarrassed, surprised, shocked, thinking, winking, cool, relaxed, delicious, kissy, confident, sleepy, silly";
const STATUS_EXPRESSIONS = new Set([
  "listening",
  "speaking",
  "loading",
  "offline",
  "待机",
  "充电",
  "唤醒",
  "休眠",
  "等待",
]);

export interface EmotionProvider {
  run(
    context: VoiceTurnContext,
    catalog: ToolCatalogResponse,
    modelResolver: ModelResolver,
  ): Promise<void>;
}

export class DefaultEmotionProvider implements EmotionProvider {
  async run(
    context: VoiceTurnContext,
    catalog: ToolCatalogResponse,
    modelResolver: ModelResolver,
  ): Promise<void> {
    if (!context.userText) return;
    // The debug flag intentionally bypasses device-tool authorization. It is
    // used by nlp-request.py to exercise the sidecar and raw frame directly;
    // regular requests still require the Runtime catalog capability.
    const capability = context.config.features?.includes(DEBUG_EMOTION_FEATURE)
      ? debugEmotionCapability()
      : resolveEmotionCapability(catalog);
    if (!capability) return;
    const emotionDescription = capability?.description || DEFAULT_EMOTION_TOOL_DESCRIPTION;
    const labels = emotionLabels(emotionDescription);
    if (labels.length === 0) return;
    try {
      const resolved = modelResolver.resolveProvider(context, {
        type: "platform",
        model: EMOTION_MODEL,
      });
      let output = "";
      const requestId = `${context.requestId}:emotion:1`;
      const request: ModelRequest = {
        modelCallId: `${context.turnId}:emotion:1`,
        purpose: "emotion",
        model: resolved.modelName,
        messages: [
          { role: "system", content: emotionPrompt(labels.join(", ")) },
          { role: "user", content: boundedText(context.userText, 2_000) },
        ],
        temperature: 0.1,
        maxTokens: 50,
        firstFrameTimeoutMs: 1_500,
        idleTimeoutMs: 1_500,
        totalTimeoutMs: 3_000,
      };
      safeModelRequestLog("official voice emotion model request", context, requestId, request);
      const handle = resolved.model.run(request, {
        onTextDelta(delta): void { output += delta; },
      }, {
        sessionId: context.sessionId,
        turnId: context.turnId,
        appId: context.config.businessAppId,
        requestId,
        cancellation: context.cancellation,
      });
      await handle.completed;
      const label = output.trim();
      if (!label || label === "无" || !labels.includes(label)) return;
      emitRaw(context.sessionId, buildToolCallFrame(
        capability!.originalName,
        { emotion: label },
        `${context.turnId}:emotion-frame`,
        capability!.protocol,
      ));
    } catch (error) {
      log.warn("emotion sidecar failed", { turnId: context.turnId, ...safeErrorFields(error) });
    }
  }
}

function debugEmotionCapability(): EmotionCapability {
  return {
    originalName: EMOTION_TOOL,
    protocol: "xiaoling",
    description: DEFAULT_EMOTION_TOOL_DESCRIPTION,
  };
}

interface EmotionCapability {
  originalName: string;
  protocol: "xiaoling" | "xiaozhi";
  description?: string;
}

function resolveEmotionCapability(catalog: ToolCatalogResponse): EmotionCapability | undefined {
  for (const capability of catalog.device_capabilities) {
    if (capability.original_name !== EMOTION_TOOL) continue;
    return {
      originalName: EMOTION_TOOL,
      protocol: capability.protocol,
      description: typeof capability.definition.function.description === "string"
        && capability.definition.function.description.trim()
        ? capability.definition.function.description.slice(0, 4_000)
        : DEFAULT_EMOTION_TOOL_DESCRIPTION,
    };
  }
  const fallback = catalog.tools.find((tool) => (
    tool.function.name === EMOTION_TOOL || tool.function.name === EMOTION_TOOL_ALIAS
  ));
  return fallback ? {
    originalName: EMOTION_TOOL,
    protocol: "xiaoling",
    description: fallback.function.description?.slice(0, 4_000) || DEFAULT_EMOTION_TOOL_DESCRIPTION,
  } : undefined;
}

export function emotionLabels(description?: string): string[] {
  if (!description) return [];
  const labels = description
    .split(/[,，、\n]/)
    .map((label) => label.trim())
    .filter((label) => label.length > 0
      && label.length <= 64
      && !/[\u0000-\u001f\u007f{}\[\]]/.test(label)
      && !STATUS_EXPRESSIONS.has(label.toLowerCase()));
  return Array.from(new Set(labels)).slice(0, 64);
}

function boundedText(value: string, maxChars: number): string {
  return value.length <= maxChars ? value : value.slice(0, maxChars);
}

export function emotionPrompt(emotionDescription: string): string {
  return `# Role
你是一位极具共情能力的表情回复助手。你的任务是深度分析对话语境，并从限定的库中匹配最精准的情绪标签。

# Constraints
1. **唯一性：** 必须且只能从【Expression Library】中选择一个，并禁止将中文表情输出为英文，如果找不到对应的表情就固定输出：无。
2. **纯净输出：** 严禁输出任何解释、标点、前缀或后缀，仅允许严格输出表情标签文本。
3. **优先级：** 若对话包含多种情感，以对话末尾的情绪意图或整体基调为准。

# Expression Library
${emotionDescription}

# Workflow
1. **语义解析：** 分析“对话内容”中的语气、关键词及情感意图，而非对话内容本身。
2. **情感映射：** 将解析结果与表情库进行匹配，找到共鸣度最高的标签。
3. **最终输出：** 仅输出选中的表情标签。

# 重要提醒
- 关注"谁在说什么"的情感，而非"发生了什么"
- 即使对话包含冲突，回复方可能是温柔/生气的，以回复方为准`;
}
