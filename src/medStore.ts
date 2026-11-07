import type { MedPlan, MedDose } from "./medTools";
import type { MedicineDraft } from "./medVision";

// ---------- 键名（与 v1.0.x 保持兼容，测试也直接依赖这些前缀） ----------

export function medsKey(deviceId: string): string {
  return `yaodao.meds.${deviceId}`;
}

export function doseKey(deviceId: string): string {
  return `yaodao.doses.${deviceId}`;
}

export function announcedKey(deviceId: string): string {
  return `yaodao.announced.${deviceId}`;
}

export function snoozeKey(deviceId: string): string {
  return `yaodao.snooze.${deviceId}`;
}

function photoDraftKey(deviceId: string): string {
  return `yaodao.photo_draft.${deviceId}`;
}

// ---------- 共享存储：Provider 与 PromptBuilder 用同一实例 ----------

declare const host: {
  kvGet(key: string): string | null;
  kvSet(key: string, value: string, ttlSecs: number | null): void;
};

export class MedStore {
  deviceKey = "global";

  load<T>(key: string, fallback: T): T {
    const raw = host.kvGet(key);
    if (!raw) return fallback;
    try {
      return JSON.parse(raw) as T;
    } catch {
      return fallback;
    }
  }

  save(key: string, value: unknown): void {
    host.kvSet(key, JSON.stringify(value), null);
  }

  remove(key: string): void {
    host.kvSet(key, "", 1);
  }

  /** 云端状态带时间戳：多实例间以 ntfy 日志的 ts 最新者为准。 */
  loadState(): { ts: number; plans: MedPlan[] } {
    const raw = this.load<{ ts: number; plans: MedPlan[] } | MedPlan[]>(medsKey(this.deviceKey), { ts: 0, plans: [] });
    if (Array.isArray(raw)) return { ts: 0, plans: raw };
    if (raw && Array.isArray(raw.plans)) return { ts: raw.ts || 0, plans: raw.plans };
    return { ts: 0, plans: [] };
  }

  saveState(ts: number, plans: MedPlan[]): void {
    this.save(medsKey(this.deviceKey), { ts, plans });
  }

  loadPlans(): MedPlan[] {
    return this.loadState().plans;
  }

  savePlans(plans: MedPlan[]): void {
    this.save(medsKey(this.deviceKey), { ts: Date.now(), plans });
  }

  loadDoses(): MedDose[] {
    return this.load<MedDose[]>(doseKey(this.deviceKey), []);
  }

  saveDoses(doses: MedDose[]): void {
    this.save(doseKey(this.deviceKey), doses);
  }

  loadAnnounced(): Record<string, true> {
    return this.load<Record<string, true>>(announcedKey(this.deviceKey), {});
  }

  saveAnnounced(map: Record<string, true>): void {
    this.save(announcedKey(this.deviceKey), map);
  }

  loadSnooze(): Record<string, number> {
    return this.load<Record<string, number>>(snoozeKey(this.deviceKey), {});
  }

  loadDraft(): MedicineDraft | null {
    return this.load<MedicineDraft | null>(photoDraftKey(this.deviceKey), null);
  }

  saveDraft(draft: MedicineDraft): void {
    this.save(photoDraftKey(this.deviceKey), draft);
  }

  clearDraft(): void {
    this.remove(photoDraftKey(this.deviceKey));
  }

  saveSnooze(map: Record<string, number>): void {
    this.save(snoozeKey(this.deviceKey), map);
  }
}

// ---------- 到期计算（纯函数，可单测） ----------

const Z8_MS = 8 * 3_600_000;

export function dayStringZ8(nowMs: number): string {
  return new Date(nowMs + Z8_MS).toISOString().slice(0, 10);
}

/** "HH:MM"（北京时间）→ 当天该时刻的 epoch ms。 */
export function slotEpochMs(dayISO: string, hhmm: string, nowMs: number): number {
  const base = Date.parse(`${dayISO}T${hhmm}:00+08:00`);
  return Number.isFinite(base) ? base : nowMs;
}

/** 由餐次文案推导兜底服药时刻；推不出来的药不做主动提醒。 */
export function fallbackSlotOf(plan: MedPlan): string | null {
  const meal = plan.meal;
  if (meal.includes("早")) return "07:30";
  if (meal.includes("午")) return "12:00";
  if (meal.includes("晚")) return "18:00";
  if (meal.includes("睡")) return "21:30";
  return null;
}

export interface PlanSlot {
  plan: MedPlan;
  index: number; // 当天第几剂（0 起）
  hhmm: string;
  epochMs: number;
}

/** 展开某天全部计划槽位（有 times 用 times；没有时用餐次兜底，每剂一个）。 */
export function expandSlots(plans: MedPlan[], dayISO: string, nowMs: number): PlanSlot[] {
  const slots: PlanSlot[] = [];
  for (const plan of plans) {
    let times = plan.times.filter(Boolean);
    if (times.length === 0) {
      const fallback = fallbackSlotOf(plan);
      if (!fallback) continue;
      times = Array.from({ length: Math.max(1, plan.per_day) }, () => fallback);
    }
    times.slice(0, Math.max(1, plan.per_day)).forEach((hhmm, index) => {
      slots.push({ plan, index, hhmm, epochMs: slotEpochMs(dayISO, hhmm, nowMs) });
    });
  }
  return slots.sort((a, b) => a.epochMs - b.epochMs);
}

export interface DueAnnouncement {
  text: string;
  markKeys: string[];
}

/**
 * 计算本轮应提醒的到期剂量（最多 2 条）。
 * 到期 = 槽位时间已过 && 该槽位尚未打卡（已打卡次数 <= 槽位序号）&& 未播报过 && 未被贪睡推迟。
 */
export function computeDueAnnouncement(
  plans: MedPlan[],
  doses: MedDose[],
  nowMs: number,
  announced: Record<string, true>,
  snooze: Record<string, number>,
  maxItems = 2,
): DueAnnouncement | null {
  const dayISO = dayStringZ8(nowMs);
  const takenByDrug = new Map<string, number>();
  for (const d of doses) {
    if (d.taken_at.startsWith(dayISO)) {
      takenByDrug.set(d.drug, (takenByDrug.get(d.drug) ?? 0) + 1);
    }
  }
  const slots = expandSlots(plans, dayISO, nowMs);
  const due: PlanSlot[] = slots.filter((slot) => {
    if (slot.epochMs > nowMs) return false;
    const taken = takenByDrug.get(slot.plan.drug) ?? 0;
    if (slot.index < taken) return false;
    const key = `${slot.plan.drug}|${dayISO}|${slot.index}`;
    if (announced[key]) return false;
    const until = snooze[key] ?? 0;
    if (until > nowMs) return false;
    return true;
  });
  if (due.length === 0) return null;
  const picked = due.slice(0, maxItems);
  const text = picked
    .map((s) => `到时间吃${s.plan.meal.includes("睡") ? "睡前" : ""}${s.plan.drug}了（${s.plan.dosage}）`)
    .join("；");
  return {
    text,
    markKeys: picked.map((s) => `${s.plan.drug}|${dayISO}|${s.index}`),
  };
}
