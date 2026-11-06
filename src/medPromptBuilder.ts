import { DefaultPromptBuilder, type PromptBuildInput } from "./prompt/defaultPromptBuilder";
import type { AgentChatMessage } from "@listenai/agent-sdk";
import { MedStore, computeDueAnnouncement } from "./medStore";

/**
 * 在默认提示词构建之上，做「到药提醒」的确定性注入：
 * 每轮对话开始时用 KV 里的计划/打卡计算到期剂量（纯代码，不依赖模型自觉），
 * 有到期剂量就在 system 消息末尾追加提醒指令，并登记已播报（防重复打扰）。
 */
export class MedPromptBuilder extends DefaultPromptBuilder {
  private readonly store: MedStore;

  constructor(store: MedStore) {
    super();
    this.store = store;
  }

  override build(input: PromptBuildInput): AgentChatMessage[] {
    const messages = super.build(input);
    let due: ReturnType<typeof computeDueAnnouncement> = null;
    try {
      const nowMs = Date.now();
      due = computeDueAnnouncement(
        this.store.loadPlans(),
        this.store.loadDoses(),
        nowMs,
        this.store.loadAnnounced(),
        this.store.loadSnooze(),
      );
      if (due) {
        const announced = this.store.loadAnnounced();
        for (const key of due.markKeys) announced[key] = true;
        this.store.saveAnnounced(announced);
      }
    } catch {
      return messages; // 提醒是尽力而为，任何异常都不影响正常对话
    }
    if (!due) return messages;
    const first = messages[0];
    if (first && typeof first.content === "string") {
      messages[0] = {
        ...first,
        content: `${first.content}\n\n【到药提醒】${due.text}\n这是系统根据用药计划计算的到药提醒，请在回复最前面先用一句话温和地提醒用户吃药（例如「到点啦，该吃降压药了」），再回答用户的问题。`,
      };
    }
    return messages;
  }
}
