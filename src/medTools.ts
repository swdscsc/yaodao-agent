import {
  LocalToolExecutor,
  type AgentToolCall,
  type AgentToolResult,
  type FunctionTool,
} from "@listenai/agent-sdk";
import { DefaultToolProvider, type ToolPreparationContext } from "./tools/defaultToolProvider";
import { runtimeClient } from "./context/listenaiContextProvider";
import { requestContext, type VoiceTurnContext } from "./types";
import type { AgentRuntimeClient } from "@listenai/agent-sdk";
import { MedStore, computeDueAnnouncement, expandSlots } from "./medStore";
import { missingFields, nextQuestion, type MedicineDraft } from "./medVision";

interface TurnRuntime {
  client: AgentRuntimeClient;
  reqCtx: ReturnType<typeof requestContext>;
  cancel: VoiceTurnContext["cancellation"];
}

// ---------- 数据结构 ----------

export interface MedPlan {
  drug: string;
  per_day: number;
  meal: string; // 饭前 / 饭后 / 空腹 / 随时
  dosage: string;
  times: string[]; // HH:MM 列表，可能为空
  created_at: string;
}

export interface MedDose {
  drug: string;
  taken_at: string;
}

const MAX_PLANS = 20;
const MAX_DOSE_LOG = 100;
const MAX_PER_DAY = 12;
const MAX_TIMES = 14;
const DOUBLE_TAKE_WINDOW_MS = 120_000; // 同药两分钟内视为误触发，不重复记

/** 时间串归一："8:5" → "08:05"，非法值（25:99 等）丢弃。 */
function normalizeTimes(values: unknown): string[] {
  const out: string[] = [];
  const list = Array.isArray(values) ? values : [];
  for (const v of list) {
    const m = /^(\d{1,2})[:：](\d{1,2})$/.exec(String(v).trim());
    if (!m) continue;
    const hh = Number(m[1]);
    const mm = Number(m[2]);
    if (hh > 23 || mm > 59) continue;
    out.push(`${String(hh).padStart(2, "0")}:${String(mm).padStart(2, "0")}`);
    if (out.length >= MAX_TIMES) break;
  }
  return out;
}

function photoDraftKey(deviceId: string): string {
  return `yaodao.photo_draft.${deviceId}`;
}

// 设备与用户都在中国，「今天」一律按北京时间（UTC+8）计算，
// 否则凌晨 0-8 点的打卡会被统计到「昨天」。
const Z8_MS = 8 * 3_600_000;

export function nowString(): string {
  return new Date(Date.now() + Z8_MS).toISOString().replace("T", " ").slice(0, 16);
}

function dayString(): string {
  return new Date(Date.now() + Z8_MS).toISOString().slice(0, 10);
}

/** 把 "YYYY-MM-DD HH:MM"（北京时间）解析回 epoch ms，用于间隔计算。 */
function parseZ8(value: string): number {
  const date = Date.parse(`${value.replace(" ", "T")}+08:00`);
  return Number.isFinite(date) ? date : 0;
}

export function describePlan(plan: MedPlan): string {
  const when = plan.times.length > 0 ? `，时间是 ${plan.times.join(" 和 ")}` : "";
  return `${plan.drug}：每天 ${plan.per_day} 次，${plan.meal}吃，一次 ${plan.dosage}${when}`;
}

// ---------- 按餐次/时段分组（适老化：开口问"早上吃什么"时更好念） ----------

export type MealSegment = "早餐" | "午餐" | "晚餐" | "睡前" | "其他";

export function mealSegmentOf(plan: MedPlan): MealSegment {
  if (plan.times.length > 0) {
    const hour = Math.min(
      ...plan.times.map((t) => parseInt(t.split(":")[0], 10) || 0),
    );
    if (hour > 0 && hour < 11) return "早餐";
    if (hour >= 11 && hour < 15) return "午餐";
    if (hour >= 15 && hour < 21) return "晚餐";
    if (hour >= 21) return "睡前";
  }
  if (plan.meal.includes("早")) return "早餐";
  if (plan.meal.includes("午")) return "午餐";
  if (plan.meal.includes("睡")) return "睡前";
  if (plan.meal.includes("晚")) return "晚餐";
  return "其他";
}

const SEGMENT_ORDER: MealSegment[] = ["早餐", "午餐", "晚餐", "睡前", "其他"];

export function groupPlans(plans: MedPlan[]): string {
  if (plans.length === 0) return "现在还没有记录。";
  const buckets = new Map<MealSegment, MedPlan[]>();
  for (const p of plans) {
    const seg = mealSegmentOf(p);
    if (!buckets.has(seg)) buckets.set(seg, []);
    buckets.get(seg)!.push(p);
  }
  return SEGMENT_ORDER.filter((s) => buckets.has(s))
    .map((s) => `${s}：${buckets.get(s)!.map(describePlan).join("；")}`)
    .join("\n");
}

// ---------- 工具定义 ----------

const medPlanSaveDef: FunctionTool = {
  type: "function",
  function: {
    name: "med_plan_save",
    description:
      "保存或更新一条用药计划。用户说出任何包含药名和服用规律的话（例如「我每天早饭后吃一片降压药」「头孢一天三次每次两粒」）时必须调用本工具，不要只靠对话记忆。相同药名再次保存视为更新。调用成功后，把返回的 confirm_text 完整念给用户，并问一句「对吗」。",
    parameters: {
      type: "object",
      properties: {
        drug: { type: "string", description: "药名，如「降压药」「阿莫西林」" },
        per_day: { type: "number", description: "每天几次，数字" },
        meal: { type: "string", description: "饭前 / 饭后 / 空腹 / 随时，四选一" },
        dosage: { type: "string", description: "每次剂量，如「一片」「两粒」「5毫升」" },
        times: {
          type: "array",
          items: { type: "string" },
          description: "具体服药时间列表，格式 HH:MM；用户没说精确时间就传空数组",
        },
      },
      required: ["drug", "per_day", "meal", "dosage"],
    },
  },
};

const medPlanListDef: FunctionTool = {
  type: "function",
  function: {
    name: "med_plan_list",
    description:
      "查询本设备已记录的全部用药计划。用户问「我要吃哪些药」「我的用药计划」「今天有什么药」时调用。返回为空时温和告知还没有记录，并举例教用户怎么建档。",
    parameters: { type: "object", properties: {} },
  },
};

const medPlanDeleteDef: FunctionTool = {
  type: "function",
  function: {
    name: "med_plan_delete",
    description:
      "删除一条用药计划。仅当用户明确说「把XX药删掉」「我停吃XX了，不用记了」时调用。用户只是问能不能停药、要不要加量时，禁止调用本工具，应建议咨询医生。",
    parameters: {
      type: "object",
      properties: {
        drug: { type: "string", description: "要删除的药名" },
      },
      required: ["drug"],
    },
  },
};

const medTakeDef: FunctionTool = {
  type: "function",
  function: {
    name: "med_take",
    description:
      "记录一次实际服药打卡。用户说「我吃了」「XX吃过了」「刚把药吃了」时，根据上下文确定药名并调用；确定不了就先问是哪种药。成功后念出返回的 confirm_text，并加一句鼓励。",
    parameters: {
      type: "object",
      properties: {
        drug: { type: "string", description: "药名" },
      },
      required: ["drug"],
    },
  },
};

const medReportDef: FunctionTool = {
  type: "function",
  function: {
    name: "med_report",
    description:
      "生成当日用药依从性小结。用户问「我今天吃药情况怎么样」「我按时吃药了吗」「这周有没有漏吃」时调用。统计今天每个药应服次数（来自计划 per_day 之和）与已打卡次数（来自打卡记录），漏服的温和提醒。返回 confirm_text 念给用户。",
    parameters: { type: "object", properties: {} },
  },
};

const medSnoozeDef: FunctionTool = {
  type: "function",
  function: {
    name: "med_snooze",
    description:
      "推迟吃药提醒。用户在收到到药提醒后说「等会儿再提醒」「先别提醒」「过10分钟再叫我」时调用。drug 传药名（不确定就传空字符串推迟全部到期药），minutes 默认 10。成功后把 confirm_text 念出来。",
    parameters: {
      type: "object",
      properties: {
        drug: { type: "string", description: "药名；空字符串表示推迟全部到期的药" },
        minutes: { type: "number", description: "推迟几分钟，默认 10" },
      },
    },
  },
};

const medDraftGetDef: FunctionTool = {
  type: "function",
  function: {
    name: "med_draft_get",
    description:
      "读取拍照建档草稿（含已识别字段与缺失项）。拍照建档的多步确认过程中，每轮都应先调用它查看当前状态；返回 missing 为空数组时说明信息已齐全，应调用 med_plan_save 落库。禁止把字段名或 JSON 念给用户。",
    parameters: { type: "object", properties: {} },
  },
};

const medDraftSetDef: FunctionTool = {
  type: "function",
  function: {
    name: "med_draft_set",
    description:
      "把用户刚确认的一个字段写进拍照建档草稿。一次只写一个字段（用户答了什么写什么），写完调用 med_draft_get 看还缺什么。只传用户确认过的字段，绝不臆测。",
    parameters: {
      type: "object",
      properties: {
        drug: { type: "string", description: "药名（仅当用户念了药名才传）" },
        per_day: { type: "number", description: "每天几次（仅当用户确认了才传）" },
        meal: { type: "string", description: "饭前/饭后/空腹/随时（仅当用户确认了才传）" },
        dosage: { type: "string", description: "每次剂量（仅当用户确认了才传）" },
        times: {
          type: "array",
          items: { type: "string" },
          description: "服药时间列表 HH:MM（仅当用户确认了才传）",
        },
      },
    },
  },
};

// ---------- Provider：每轮绑定设备 ID ----------

function textResult(call: AgentToolCall, text: string, isError = false): AgentToolResult {
  return {
    callId: call.id,
    content: [{ type: "text", text }],
    isError,
    control: { agentStop: false },
    artifacts: [],
  };
}

export class MedToolProvider extends DefaultToolProvider {
  // prepare() 每轮更新；本产品当前一台设备，并发竞争可接受
  private readonly store: MedStore;
  private rt: TurnRuntime | null = null;

  constructor(store: MedStore = new MedStore()) {
    super({
      localTools: [
        { definition: medPlanSaveDef, handlerId: "med_plan_save" },
        { definition: medPlanListDef, handlerId: "med_plan_list" },
        { definition: medPlanDeleteDef, handlerId: "med_plan_delete" },
        { definition: medTakeDef, handlerId: "med_take" },
        { definition: medReportDef, handlerId: "med_report" },
        { definition: medSnoozeDef, handlerId: "med_snooze" },
        { definition: medDraftGetDef, handlerId: "med_draft_get" },
        { definition: medDraftSetDef, handlerId: "med_draft_set" },
      ],
      localExecutors: {
        med_plan_save: new LocalToolExecutor({
          handler: (call) => this.onSave(call),
        }),
        med_plan_list: new LocalToolExecutor({
          handler: (call) => this.onList(call),
        }),
        med_plan_delete: new LocalToolExecutor({
          handler: (call) => this.onDelete(call),
        }),
        med_take: new LocalToolExecutor({
          handler: (call) => this.onTake(call),
        }),
        med_report: new LocalToolExecutor({
          handler: (call) => this.onReport(call),
        }),
        med_snooze: new LocalToolExecutor({
          handler: (call) => this.onSnooze(call),
        }),
        med_draft_get: new LocalToolExecutor({
          handler: (call) => this.onDraftGet(call),
        }),
        med_draft_set: new LocalToolExecutor({
          handler: (call) => this.onDraftSet(call),
        }),
      },
    });
    this.store = store;
  }

  override prepare(
    context: VoiceTurnContext,
    policyContext?: ToolPreparationContext,
  ): ReturnType<DefaultToolProvider["prepare"]> {
    this.store.deviceKey = context.deviceId || "global";
    this.rt = {
      client: runtimeClient(context),
      reqCtx: requestContext(context, "med-tools"),
      cancel: context.cancellation,
    };
    return super.prepare(context, policyContext);
  }

  // KV 是主存储但按运行实例隔离；同步镜像一份全量计划快照到平台长期记忆，
  // KV 未命中时用记忆兜底。镜像失败静默忽略（尽力而为）。
  private mirrorSnapshot(plans: MedPlan[]): void {
    const rt = this.rt;
    if (!rt) return;
    const body = plans.length
      ? plans.map((p) => `【用药计划】${describePlan(p)}`).join("；")
      : "【用药计划】当前没有任何用药计划";
    rt.client
      .storeMemory(
        {
          messages: [{ role: "user", content: `${body}（快照时间 ${nowString()}）` }],
          metadata: { kind: "med_plan_snapshot", count: plans.length },
        },
        rt.reqCtx,
        rt.cancel,
      )
      .catch(() => undefined);
  }

  private async recallPlans(): Promise<string> {
    const rt = this.rt;
    if (!rt) return "";
    try {
      const response = await rt.client.recallMemory(
        { query: "用药计划 药名 每天几次 饭前饭后 剂量" },
        rt.reqCtx,
        rt.cancel,
      );
      const text = response.memory_text ?? "";
      return text.includes("【用药计划】") ? text : "";
    } catch {
      return "";
    }
  }

  private onSave(call: AgentToolCall): AgentToolResult {
    let args: Partial<MedPlan>;
    try {
      args = JSON.parse(call.arguments || "{}") as Partial<MedPlan>;
    } catch {
      return textResult(call, "参数不是合法 JSON", true);
    }
    const drug = String(args.drug ?? "").trim().slice(0, 40);
    const perDayRaw = Number(args.per_day);
    const meal = String(args.meal ?? "随时").trim().slice(0, 20) || "随时";
    const dosage = String(args.dosage ?? "").trim().slice(0, 20);
    const times = normalizeTimes(args.times);
    const perDay = Math.min(Math.round(perDayRaw), MAX_PER_DAY);
    if (!drug || !Number.isFinite(perDayRaw) || perDay <= 0 || !dosage) {
      return textResult(call, "缺少药名、每天次数或剂量，请向用户确认后重试", true);
    }
    const plans = this.store.loadPlans();
    const plan: MedPlan = {
      drug,
      per_day: perDay,
      meal,
      dosage,
      times,
      created_at: nowString(),
    };
    const index = plans.findIndex((p) => p.drug === drug);
    if (index >= 0) plans[index] = plan;
    else if (plans.length >= MAX_PLANS) {
      return textResult(call, `用药计划已满 ${MAX_PLANS} 条，请先删除不需要的`, true);
    } else plans.push(plan);
    this.store.savePlans(plans);
    this.mirrorSnapshot(plans);
    // 拍照建档闭环：草稿里的药已正式落库，清理暂存，避免下次误用旧草稿。
    const draftRaw = host.kvGet(photoDraftKey(this.store.deviceKey));
    if (draftRaw) {
      try {
        const draft = JSON.parse(draftRaw) as { drug?: string };
        if (!draft.drug || draft.drug === drug) host.kvSet(photoDraftKey(this.store.deviceKey), "", 1);
      } catch {
        host.kvSet(photoDraftKey(this.store.deviceKey), "", 1);
      }
    }
    return textResult(
      call,
      JSON.stringify({
        ok: true,
        confirm_text: `我记下了：${describePlan(plan)}。您听听对不对？`,
        total: plans.length,
      }),
    );
  }

  private async onList(call: AgentToolCall): Promise<AgentToolResult> {
    const plans = this.store.loadPlans();
    if (plans.length === 0) {
      const memoryText = await this.recallPlans();
      if (memoryText) {
        return textResult(
          call,
          JSON.stringify({
            ok: true,
            empty: false,
            source: "memory",
            confirm_text: `根据我的记忆，${memoryText.replace(/【用药计划】/g, "").trim()}。`,
          }),
        );
      }
      return textResult(
        call,
        JSON.stringify({
          ok: true,
          empty: true,
          confirm_text: "现在还没有记录。您可以跟我说一句，比如「我每天早饭后吃一片降压药」，我就帮您记上了。",
        }),
      );
    }
    return textResult(
      call,
      JSON.stringify({
        ok: true,
        empty: false,
        confirm_text: `您一共有 ${plans.length} 个用药计划：\n${groupPlans(plans)}`,
        plans,
      }),
    );
  }

  private onDelete(call: AgentToolCall): AgentToolResult {
    let args: { drug?: string };
    try {
      args = JSON.parse(call.arguments || "{}") as { drug?: string };
    } catch {
      return textResult(call, "参数不是合法 JSON", true);
    }
    const drug = String(args.drug ?? "").trim();
    const plans = this.store.loadPlans();
    const next = plans.filter((p) => p.drug !== drug);
    if (next.length === plans.length) {
      return textResult(call, `没有找到名为「${drug}」的用药计划`, true);
    }
    this.store.savePlans(next);
    this.mirrorSnapshot(next);
    return textResult(
      call,
      JSON.stringify({ ok: true, confirm_text: `好，「${drug}」的用药计划已经删掉了。` }),
    );
  }

  private onTake(call: AgentToolCall): AgentToolResult {
    let args: { drug?: string };
    try {
      args = JSON.parse(call.arguments || "{}") as { drug?: string };
    } catch {
      return textResult(call, "参数不是合法 JSON", true);
    }
    const drug = String(args.drug ?? "").trim().slice(0, 40);
    if (!drug) return textResult(call, "缺少药名，请先向用户确认是哪种药", true);
    const doses = this.store.loadDoses();
    // 重复打卡防护：同一药两分钟内视为语音重复/回声，不重复记录，
    // 避免依从性统计虚高（医疗场景宁可少记，让用户确认后再补）。
    const lastSame = doses.filter((d) => d.drug === drug).at(-1);
    if (lastSame && Date.now() - parseZ8(lastSame.taken_at) < DOUBLE_TAKE_WINDOW_MS) {
      return textResult(
        call,
        JSON.stringify({
          ok: true,
          duplicate: true,
          confirm_text: `我刚才已经记过一次${drug}了。如果您确实又吃了一次，跟我说「${drug}再记一次」，我再帮您补上。`,
        }),
      );
    }
    doses.push({ drug, taken_at: nowString() });
    while (doses.length > MAX_DOSE_LOG) doses.shift();
    this.store.saveDoses(doses);
    const known = this.store.loadPlans().some((p) => p.drug === drug);
    const tail = known ? "" : "（这个药我还没有建档，需要我记一下它的服用规律吗？）";
    return textResult(
      call,
      JSON.stringify({
        ok: true,
        confirm_text: `真棒，${drug}这次吃上了，我记好了${tail}`,
        taken_count: doses.length,
      }),
    );
  }

  // 当日用药依从性小结：纯本地 KV 计算，无需外部服务。
  // todayISO 可注入（测试用）；线上默认按北京时间算「今天」。
  private onReport(call: AgentToolCall, todayISO?: string): AgentToolResult {
    const plans = this.store.loadPlans();
    const doses = this.store.loadDoses();
    const today = todayISO ?? dayString();
    const takenToday = doses.filter((d) => d.taken_at.startsWith(today));
    const takenByDrug = new Map<string, number>();
    for (const d of takenToday) {
      takenByDrug.set(d.drug, (takenByDrug.get(d.drug) ?? 0) + 1);
    }
    if (plans.length === 0) {
      if (takenToday.length === 0) {
        return textResult(
          call,
          JSON.stringify({
            ok: true,
            empty: true,
            confirm_text:
              "现在还没有用药计划，我没法统计哦。您先跟我说一句服药规律，比如「我每天早饭后吃一片降压药」，我就帮您记上。",
          }),
        );
      }
      const names = [...new Set(takenToday.map((d) => d.drug))];
      return textResult(
        call,
        JSON.stringify({
          ok: true,
          empty: false,
          confirm_text: `今天您打卡了 ${takenToday.length} 次：${names.join("、")}。不过这些药还没建档，我可以帮您把服用规律记下来，要吗？`,
        }),
      );
    }
    const lines = plans.map((p) => {
      const expected = p.per_day;
      const taken = takenByDrug.get(p.drug) ?? 0;
      return taken >= expected
        ? `${p.drug}：今天应服 ${expected} 次，已服 ${taken} 次，齐了`
        : `${p.drug}：今天应服 ${expected} 次，已服 ${taken} 次，还差 ${expected - taken} 次`;
    });
    const totalExpected = plans.reduce((sum, p) => sum + p.per_day, 0);
    const confirm_text = `今天用药小结：共 ${plans.length} 种药，计划 ${totalExpected} 次，已打卡 ${takenToday.length} 次。\n${lines.join("\n")}`;
    return textResult(call, JSON.stringify({ ok: true, confirm_text }));
  }

  // 稍后提醒：把当前已到期、尚未打卡的槽位推迟 N 分钟后重新播报。
  private onSnooze(call: AgentToolCall): AgentToolResult {
    let args: { drug?: string; minutes?: number };
    try {
      args = JSON.parse(call.arguments || "{}") as { drug?: string; minutes?: number };
    } catch {
      return textResult(call, "参数不是合法 JSON", true);
    }
    const drug = String(args.drug ?? "").trim();
    const minutes = Math.min(Math.max(Math.round(Number(args.minutes) || 10), 5), 120);
    const nowMs = Date.now();
    const dayISO = dayString();
    const plans = this.store.loadPlans();
    const doses = this.store.loadDoses();
    const takenByDrug = new Map<string, number>();
    for (const d of doses) {
      if (d.taken_at.startsWith(dayISO)) {
        takenByDrug.set(d.drug, (takenByDrug.get(d.drug) ?? 0) + 1);
      }
    }
    const eligible = expandSlots(plans, dayISO, nowMs).filter((slot) => {
      if (slot.epochMs > nowMs) return false;
      if ((takenByDrug.get(slot.plan.drug) ?? 0) > slot.index) return false;
      return !drug || slot.plan.drug === drug;
    });
    if (eligible.length === 0) {
      return textResult(
        call,
        JSON.stringify({ ok: true, nothing_due: true, confirm_text: "现在没有到点的药，您放心。到点我会喊您的。" }),
      );
    }
    const snooze = this.store.loadSnooze();
    const announced = this.store.loadAnnounced();
    for (const slot of eligible) {
      const key = `${slot.plan.drug}|${dayISO}|${slot.index}`;
      snooze[key] = nowMs + minutes * 60_000;
      delete announced[key]; // 贪睡到期后允许重新播报
    }
    this.store.saveSnooze(snooze);
    this.store.saveAnnounced(announced);
    const names = [...new Set(eligible.map((s) => s.plan.drug))].join("、");
    return textResult(
      call,
      JSON.stringify({
        ok: true,
        confirm_text: `好，${names}我等 ${minutes} 分钟后再提醒您。您先忙。`,
      }),
    );
  }

  private onDraftGet(call: AgentToolCall): AgentToolResult {
    const draft = this.store.loadDraft();
    if (!draft || !draft.is_medicine) {
      return textResult(
        call,
        JSON.stringify({
          ok: false,
          confirm_text: "现在没有进行中的拍照建档。请用户重新拍一张药盒照片，或直接口述建档。",
        }),
      );
    }
    const missing = missingFields(draft);
    const next = nextQuestion(draft);
    return textResult(
      call,
      JSON.stringify({
        ok: true,
        draft: {
          drug: draft.drug ?? "",
          per_day: draft.per_day ?? 0,
          meal: draft.meal ?? "",
          dosage: draft.dosage ?? "",
          times: draft.times ?? [],
        },
        missing,
        next_question: next || "",
        confirm_text: missing.length
          ? `草稿状态：药名${draft.drug ? "已识别" : "缺失"}、次数${draft.per_day ? "已确认" : "缺失"}、餐次${draft.meal ? "已确认" : "缺失"}、剂量${draft.dosage ? "已确认" : "缺失"}。下一句只问：${next}`
          : "全部确认齐了，请调用 med_plan_save 落库。",
      }),
    );
  }

  private onDraftSet(call: AgentToolCall): AgentToolResult {
    let patch: Partial<MedicineDraft>;
    try {
      patch = JSON.parse(call.arguments || "{}") as Partial<MedicineDraft>;
    } catch {
      return textResult(call, "参数不是合法 JSON", true);
    }
    const draft = this.store.loadDraft();
    if (!draft || !draft.is_medicine) {
      return textResult(call, "没有进行中的拍照建档草稿", true);
    }
    if (typeof patch.drug === "string" && patch.drug.trim()) draft.drug = patch.drug.trim().slice(0, 40);
    if (typeof patch.per_day === "number" && patch.per_day > 0 && patch.per_day <= MAX_PER_DAY) {
      draft.per_day = Math.round(patch.per_day);
    }
    if (typeof patch.meal === "string" && patch.meal.trim()) draft.meal = patch.meal.trim().slice(0, 20);
    if (typeof patch.dosage === "string" && patch.dosage.trim()) draft.dosage = patch.dosage.trim().slice(0, 20);
    if (Array.isArray(patch.times)) draft.times = normalizeTimes(patch.times);
    this.store.saveDraft(draft);
    const missing = missingFields(draft);
    return textResult(
      call,
      JSON.stringify({
        ok: true,
        missing,
        confirm_text: missing.length
          ? `已记录。还缺 ${missing.length} 项。`
          : "全部确认齐了，请调用 med_plan_save 落库。",
      }),
    );
  }
}
