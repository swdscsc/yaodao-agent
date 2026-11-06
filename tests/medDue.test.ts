import { describe, it, beforeEach } from "node:test";
import assert from "node:assert/strict";
import {
  MedStore,
  computeDueAnnouncement,
  expandSlots,
  fallbackSlotOf,
  dayStringZ8,
  slotEpochMs,
} from "../src/medStore";
import type { MedPlan, MedDose } from "../src/medTools";

// MedStore 依赖平台 host 全局，用内存 KV 顶替。
const store: Record<string, string> = {};
const mockHost = {
  kvGet: (key: string): string | null => store[key] ?? null,
  kvSet: (key: string, value: string): void => {
    store[key] = value;
  },
};

// 固定"现在"：北京时间 2026-11-08 08:05（对应 UTC 00:05）
const NOW = Date.parse("2026-11-08T00:05:00Z");

function plan(overrides: Partial<MedPlan> = {}): MedPlan {
  return {
    drug: "降压药",
    per_day: 1,
    meal: "早饭后",
    dosage: "一片",
    times: ["08:00"],
    created_at: "2026-11-07 20:00",
    ...overrides,
  };
}

describe("expandSlots / fallbackSlotOf", () => {
  it("有 times 时按 times 展开", () => {
    const slots = expandSlots([plan({ times: ["08:00", "20:00"], per_day: 2 })], "2026-11-08", NOW);
    assert.equal(slots.length, 2);
    assert.equal(slots[0].hhmm, "08:00");
    assert.equal(slots[1].hhmm, "20:00");
  });

  it("无 times 时按餐次兜底（早饭后 → 07:30）", () => {
    const p = plan({ times: [], meal: "早饭后" });
    assert.equal(fallbackSlotOf(p), "07:30");
    const slots = expandSlots([p], "2026-11-08", NOW);
    assert.equal(slots.length, 1);
  });

  it("推不出时刻的药（随时）不做主动提醒", () => {
    const slots = expandSlots([plan({ times: [], meal: "随时" })], "2026-11-08", NOW);
    assert.equal(slots.length, 0);
  });

  it("slotEpochMs 按北京时间解析", () => {
    const ms = slotEpochMs("2026-11-08", "08:00", NOW);
    assert.equal(ms, Date.parse("2026-11-08T08:00:00+08:00"));
  });

  it("dayStringZ8 用北京时间切日", () => {
    // UTC 2026-11-07T20:00 = 北京 2026-11-08 04:00
    assert.equal(dayStringZ8(Date.parse("2026-11-07T20:00:00Z")), "2026-11-08");
  });
});

describe("computeDueAnnouncement", () => {
  beforeEach(() => {
    for (const k of Object.keys(store)) delete store[k];
    (globalThis as unknown as { host: unknown }).host = mockHost;
  });

  it("到点未打卡 → 提醒", () => {
    // 08:00 的药，现在 08:05，没打卡
    const due = computeDueAnnouncement([plan()], [], NOW, {}, {});
    assert.ok(due, "应有到期提醒");
    assert.ok(due!.text.includes("降压药"));
    assert.equal(due!.markKeys.length, 1);
  });

  it("未到点 → 不提醒", () => {
    const due = computeDueAnnouncement([plan({ times: ["20:00"] })], [], NOW, {}, {});
    assert.equal(due, null);
  });

  it("已打卡 → 不提醒", () => {
    const doses: MedDose[] = [{ drug: "降压药", taken_at: "2026-11-08 07:58" }];
    const due = computeDueAnnouncement([plan()], doses, NOW, {}, {});
    assert.equal(due, null);
  });

  it("已播报过 → 不重复提醒", () => {
    const key = "降压药|2026-11-08|0";
    const due = computeDueAnnouncement([plan()], [], NOW, { [key]: true }, {});
    assert.equal(due, null);
  });

  it("贪睡中 → 不提醒；贪睡到期 → 恢复提醒", () => {
    const key = "降压药|2026-11-08|0";
    const snoozed = computeDueAnnouncement([plan()], [], NOW, {}, { [key]: NOW + 60_000 });
    assert.equal(snoozed, null);
    const expired = computeDueAnnouncement([plan()], [], NOW + 120_000, {}, { [key]: NOW + 60_000 });
    assert.ok(expired, "贪睡过期后应再次提醒");
  });

  it("多剂药按槽位序号判断：第 1 剂已吃，第 2 剂到点才提醒", () => {
    const p = plan({ times: ["08:00", "20:00"], per_day: 2 });
    const doses: MedDose[] = [{ drug: "降压药", taken_at: "2026-11-08 08:01" }];
    const due = computeDueAnnouncement([p], doses, NOW, {}, {});
    assert.equal(due, null, "08:05 时第 1 剂已吃、第 2 剂未到，不应提醒");
  });

  it("一次最多提醒 2 条", () => {
    const plans = [
      plan({ drug: "A", times: ["08:00"] }),
      plan({ drug: "B", times: ["08:01"] }),
      plan({ drug: "C", times: ["08:02"] }),
    ];
    const due = computeDueAnnouncement(plans, [], NOW, {}, {});
    assert.ok(due);
    assert.equal(due!.markKeys.length, 2);
  });

  it("per_day 大于 times 数量时按 per_day 补兜底槽", () => {
    const p = plan({ times: [], meal: "早饭后", per_day: 2 });
    const slots = expandSlots([p], "2026-11-08", NOW);
    assert.equal(slots.length, 2, "早饭后兜底时刻 × 2 剂");
  });
});

describe("MedStore（mock host）", () => {
  beforeEach(() => {
    for (const k of Object.keys(store)) delete store[k];
    (globalThis as unknown as { host: unknown }).host = mockHost;
  });

  it("计划读写与设备隔离", () => {
    const s = new MedStore();
    s.deviceKey = "dev1";
    s.savePlans([plan()]);
    assert.ok(store["yaodao.meds.dev1"], "应写入 dev1 的 KV");
    assert.ok(store["yaodao.meds.dev1"].includes("降压药"));
    s.deviceKey = "dev2";
    assert.deepEqual(s.loadPlans(), []);
  });

  it("announced / snooze 读写", () => {
    const s = new MedStore();
    s.saveAnnounced({ "a|b|0": true });
    s.saveSnooze({ "a|b|0": 123 });
    assert.deepEqual(s.loadAnnounced(), { "a|b|0": true });
    assert.deepEqual(s.loadSnooze(), { "a|b|0": 123 });
  });
});
