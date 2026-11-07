import type { ImageTurnHandler, ImageTurnResult } from "./image/imageTurnHandler";
import type { ModelResolver } from "./model/configModelResolver";
import type { VoiceTurnContext } from "./types";
/** 平台多模态视觉模型：官方标准 API 指定图片输入必须用它（实测识别药盒成功）。 */
const MEDICINE_VISION_FALLBACK_MODEL = "spark-vision-preview-1.0";
import { asAgentError, log, normalizeClosedToolContent, type AgentChatMessage } from "@listenai/agent-sdk";
import { MedStore } from "./medStore";
import { describePlan, nowString, type MedPlan } from "./medTools";
import {
  MEDICINE_VISION_PROMPT,
  draftSummary,
  draftToHistoryMarker,
  nextQuestion,
  noMedicineAnswer,
  parseVisionOutput,
  type MedicineDraft,
} from "./medVision";

/**
 * 药到专属的「拍照识别药」处理器。
 *
 * 流程：图片归一化 → 调视觉模型（带药品识别 system prompt，要求输出结构化 JSON）
 * → 解析成草稿 → 口语化念出已识别内容 + 就缺失项一项一项确认（多步确认）
 * → 全部确认后由 med_plan_save 落库（落库发生在后续语音轮次）。
 *
 * 无论图片来自设备拍照（take_photo 设备能力回传）还是直接通过 nlu.custom.image 传入，
 * 都会走到这里。
 */
export class MedicinePhotoHandler implements ImageTurnHandler {
  private readonly store: MedStore;

  constructor(store: MedStore = new MedStore()) {
    this.store = store;
  }

  async run(
    context: VoiceTurnContext,
    image: string,
    modelResolver: ModelResolver,
    onDelta: (text: string) => void,
  ): Promise<ImageTurnResult> {
    // 防卡死总开关：图片轮任何异常都必须落到一句可念的兜底话，
    // 否则设备 UI 会停在「识别中」等不到任何回复帧。
    try {
      return await this.runInner(context, image, modelResolver, onDelta);
    } catch (error) {
      const e = asAgentError(error);
      log.warn("medicine photo handler failed", { code: e.code, turnId: context.turnId });
      if (e.code === "AGENT_RESOURCE_FORBIDDEN") {
        return {
          answer: "抱歉，我暂时没法看图识别，您直接告诉我药名和吃法，我帮您记上就好。",
          messages: [],
        };
      }
      return {
        answer: "照片我一时没看清，您直接说药名和每天吃几次，我帮您记上就行。",
        messages: [],
      };
    }
  }

  private async runInner(
    context: VoiceTurnContext,
    image: string,
    modelResolver: ModelResolver,
    onDelta: (text: string) => void,
  ): Promise<ImageTurnResult> {
    log.info("medicine photo turn started", { turnId: context.turnId, imageBytes: image.length });
    // 1) 归一化图片来源（兼容 data:base64 与 https url）
    const normalized = normalizeClosedToolContent(
      image.startsWith("data:")
        ? { type: "image", kind: "input", data: image }
        : { type: "image", kind: "input", url: image },
    );
    if (!normalized || normalized.type !== "image") {
      return {
        answer: "这张图片我有点看不清，您直接告诉我药名和吃法，我帮您记上就行。",
        messages: [],
      };
    }
    const src = (normalized.url ?? normalized.data) as string;

    // 2) 解析视觉模型：优先 sidecars.vision（服务端下发），
    //    否则用平台多模态模型 spark-vision-preview-1.0（官方标准 API
    //    指定图片输入必须用此模型；doubao 等文本模型经平台代理收不到图）。
    const runtimeModel = context.config.runtime.model;
    const provider =
      runtimeModel.sidecars?.vision ??
      { type: "platform", model: MEDICINE_VISION_FALLBACK_MODEL };
    const resolved = modelResolver.resolveProvider(context, provider);
    const config = context.config.runtime.model;

    const messages: AgentChatMessage[] = [
      { role: "system", content: MEDICINE_VISION_PROMPT },
      {
        role: "user",
        content: [
          {
            type: "text",
            text: context.userText || "请识别这张药品照片上的用药信息",
          },
          { type: "image_url", image_url: { url: src } },
        ],
      },
    ];

    try {
      const handle = resolved.model.run(
        {
          modelCallId: `${context.turnId}:vision`,
          purpose: "vision",
          model: resolved.modelName,
          messages: messages as never,
          temperature: config.temperature,
          maxTokens: config.maxTokens,
          firstFrameTimeoutMs: 15_000,
          idleTimeoutMs: 30_000,
          totalTimeoutMs: config.timeoutMs ?? 120_000,
        },
        {
          // 不把视觉模型的原始输出（JSON 字段名等）流给 TTS；
          // 解析完成后再把策展文本一次性经 onDelta 写出。
          onTextDelta: () => {},
        },
        {
          sessionId: context.sessionId,
          turnId: context.turnId,
          appId: context.config.businessAppId,
          requestId: `${context.requestId}:vision`,
          cancellation: context.cancellation,
        },
      );
      const result = await handle.completed;
      const draft: MedicineDraft = parseVisionOutput(result.text);

      // 3) 持久化草稿：作为跨轮确认的可靠状态（历史被裁剪时兜底）
      host.kvSet(`yaodao.photo_draft.${context.deviceId || "global"}`, JSON.stringify(draft), null);

      if (!draft.is_medicine) {
        const fallbackAnswer = noMedicineAnswer();
        onDelta(fallbackAnswer);
        return { answer: fallbackAnswer, messages: photoHistory(src, draft) };
      }

      const summary = draftSummary(draft);
      const next = nextQuestion(draft);
      let answer: string;
      if (next) {
        answer = `我帮您看了看照片。${summary} 我再跟您确认一下——${next}`;
      } else {
        // 草稿齐全：直接落库，省一轮对话
        const plans = this.store.loadPlans();
        const plan: MedPlan = {
          drug: draft.drug!,
          per_day: draft.per_day!,
          meal: draft.meal!,
          dosage: draft.dosage!,
          times: draft.times ?? [],
          created_at: nowString(),
        };
        const index = plans.findIndex((p) => p.drug === plan.drug);
        if (index >= 0) plans[index] = plan;
        else plans.push(plan);
        this.store.savePlans(plans);
        this.store.clearDraft();
        answer = `记好了：${describePlan(plan)}。您听听对不对？`;
      }
      onDelta(answer);
      return { answer, messages: photoHistory(src, draft) };
    } catch (error) {
      const e = asAgentError(error);
      if (e.code === "AGENT_RESOURCE_FORBIDDEN") {
        return {
          answer: "抱歉，我暂时没法看图识别，您直接告诉我药名和吃法，我帮您记上就好。",
          messages: [],
        };
      }
      // 其它错误：降级为人工口述建档，不中断体验
      return {
        answer: "照片我一时没看清，您直接说药名和每天吃几次，我帮您记上就行。",
        messages: [],
      };
    }
  }
}

function photoHistory(src: string, draft: MedicineDraft): AgentChatMessage[] {
  return [
    {
      role: "user",
      content: [
        { type: "text", text: "（用户拍了一张药品照片）" },
        { type: "image_url", image_url: { url: src } },
      ],
    },
    { role: "assistant", content: draftToHistoryMarker(draft) },
  ];
}
