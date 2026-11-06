import { describe, it, beforeEach } from "node:test";
import assert from "node:assert/strict";
import {
  describePlan,
  groupPlans,
  mealSegmentOf,
  MedToolProvider,
  type MedPlan,
} from "../src/medTools";

// 平台运行时全局 `host` 在测试环境不存在，用内存 KV 顶替。
const store: Record<string, string> = {};
const mockHost = {
  kvGet: (key: string): string | null => store[key] ?? null,
  kvSet: (key: string, value: string): void => {
    store[key] = value;
  },
};

function makeProvider(): MedToolProvider {
  return new MedToolProvider();
}

function jsonOf(result: { content: Array<{ type: string; text: string }> }): any {
  return JSON.parse(result.content[0].text);
}

describe("describePlan", () => {
  it("描述带具体时间的计划", () => {
    const plan: MedPlan = {
      drug: "降压药",
      per_day: 1,
      meal: "早饭后",
      dosage: "一片",
      times: ["08:00"],
      created_at: "2026-10-30 08:00",
    };
    assert.equal(
      describePlan(plan),
      "降压药：每天 1 次，早饭后吃，一次 一片，时间是 08:00",
    );
  });

  it("描述无具体时间的计划", () => {
    const plan: MedPlan = {
      drug: "维生素",
      per_day: 2,
      meal: "饭后",
      dosage: "一粒",
      times: [],
      created_at: "2026-10-30 08:00",
    };
    assert.equal(describePlan(plan), "维生素：每天 2 次，饭后吃，一次 一粒");
  });
});

describe("mealSegmentOf / groupPlans", () => {
  it("按具体时间落时段", () => {
    assert.equal(mealSegmentOf({ ...base(), times: ["07:30"] }), "早餐");
    assert.equal(mealSegmentOf({ ...base(), times: ["12:30"] }), "午餐");
    assert.equal(mealSegmentOf({ ...base(), times: ["19:00"] }), "晚餐");
    assert.equal(mealSegmentOf({ ...base(), times: ["22:00"] }), "睡前");
  });

  it("无时间时按饭前饭后落餐次", () => {
    assert.equal(mealSegmentOf({ ...base(), meal: "早饭前" }), "早餐");
    assert.equal(mealSegmentOf({ ...base(), meal: "睡前" }), "睡前");
    assert.equal(mealSegmentOf({ ...base(), meal: "随时" }), "其他");
  });

  it("分组后按 早/午/晚/睡前/其他 顺序输出", () => {
    const plans: MedPlan[] = [
      { ...base(), drug: "A", meal: "晚饭后", times: [] },
      { ...base(), drug: "B", meal: "早饭后", times: [] },
      { ...base(), drug: "C", meal: "午饭后", times: [] },
    ];
    const grouped = groupPlans(plans);
    assert.ok(grouped.indexOf("早餐：") < grouped.indexOf("午餐："));
    assert.ok(grouped.indexOf("午餐：") < grouped.indexOf("晚餐："));
    assert.ok(grouped.includes("早餐：B："));
  });
});

describe("MedToolProvider 关键路径（mock host）", () => {
  beforeEach(() => {
    for (const k of Object.keys(store)) delete store[k];
    (globalThis as any).host = mockHost;
  });

  it("建档 -> 查询(分组) -> 打卡 -> 依从性小结", async () => {
    const p = makeProvider();
    const save = (p as any).onSave({
      id: "1",
      arguments: JSON.stringify({
        drug: "降压药",
        per_day: 1,
        meal: "早饭后",
        dosage: "一片",
        times: ["08:00"],
      }),
    });
    const saveJson = jsonOf(save);
    assert.equal(saveJson.ok, true);
    assert.ok(saveJson.confirm_text.includes("降压药"));

    const list = await (p as any).onList({ id: "2", arguments: "{}" });
    const listJson = jsonOf(list);
    assert.equal(listJson.empty, false);
    assert.ok(listJson.confirm_text.includes("早餐："));

    const take = (p as any).onTake({ id: "3", arguments: JSON.stringify({ drug: "降压药" }) });
    const takeJson = jsonOf(take);
    assert.equal(takeJson.ok, true);
    assert.ok(takeJson.confirm_text.includes("吃上了"));

    const report = (p as any).onReport({ id: "4", arguments: "{}" });
    const reportJson = jsonOf(report);
    assert.ok(reportJson.confirm_text.includes("今天用药小结"));
    assert.ok(reportJson.confirm_text.includes("已打卡 1 次"));
  });

  it("缺字段建档返回错误", () => {
    const p = makeProvider();
    const bad = (p as any).onSave({ id: "5", arguments: JSON.stringify({ drug: "X" }) });
    assert.equal(bad.isError, true);
    assert.ok(bad.content[0].text.includes("缺少"));
  });

  it("输入钳制：per_day 封顶、时间归一、字段截断", () => {
    const p = makeProvider();
    const saved = (p as any).onSave({
      id: "6",
      arguments: JSON.stringify({
        drug: "阿".repeat(50),
        per_day: 99,
        meal: "饭后",
        dosage: "一".repeat(30) + "片",
        times: ["8:5", "bad", "23:00", "25:99"],
      }),
    });
    const json = jsonOf(saved);
    assert.equal(json.ok, true);
    const plan = JSON.parse(store["yaodao.meds.global"])[0];
    assert.equal(plan.drug.length, 40, "药名截断到 40 字");
    assert.equal(plan.per_day, 12, "每天次数封顶 12");
    assert.equal(plan.dosage.length, 20, "剂量截断到 20 字");
    assert.deepEqual(plan.times, ["08:05", "23:00"], "非法与越界时间被过滤/归一");
  });

  it("重复打卡防护：两分钟内同药不重复记", () => {
    const p = makeProvider();
    (p as any).onTake({ id: "7", arguments: JSON.stringify({ drug: "降压药" }) });
    const dosesAfterFirst = JSON.parse(store["yaodao.doses.global"]).length;
    const again = (p as any).onTake({ id: "8", arguments: JSON.stringify({ drug: "降压药" }) });
    const json = jsonOf(again);
    assert.equal(json.duplicate, true);
    assert.equal(JSON.parse(store["yaodao.doses.global"]).length, dosesAfterFirst, "不应新增记录");
    assert.ok(json.confirm_text.includes("已经记过"), "应提醒而不是默默再记");
  });

  it("依从性小结按北京时间算「今天」（注入日期验证）", () => {
    const p = makeProvider();
    (p as any).onSave({
      id: "9",
      arguments: JSON.stringify({ drug: "降压药", per_day: 2, meal: "饭后", dosage: "一片" }),
    });
    // 直接写入一条北京时间 11-08 早上 7 点的打卡（对应 UTC 11-07 23:30）
    store["yaodao.doses.global"] = JSON.stringify([
      { drug: "降压药", taken_at: "2026-11-08 07:30" },
    ]);
    // 用 UTC 日期 11-07 统计应查不到；用北京时间 11-08 应查到
    const utcReport = jsonOf((p as any).onReport({ id: "10", arguments: "{}" }, "2026-11-07"));
    assert.ok(utcReport.confirm_text.includes("已服 0 次"), "UTC 日期不应统计到");
    const z8Report = jsonOf((p as any).onReport({ id: "11", arguments: "{}" }, "2026-11-08"));
    assert.ok(z8Report.confirm_text.includes("已服 1 次"), "北京时间应统计到");
  });

  it("有打卡但没建档时，小结报打卡次数而不是拒绝统计", () => {
    const p = makeProvider();
    store["yaodao.doses.global"] = JSON.stringify([
      { drug: "感冒药", taken_at: "2026-11-08 09:00" },
    ]);
    const report = jsonOf(
      (p as any).onReport({ id: "12", arguments: "{}" }, "2026-11-08"),
    );
    assert.equal(report.empty, false);
    assert.ok(report.confirm_text.includes("感冒药"));
    assert.ok(report.confirm_text.includes("还没建档"));
  });
});

function base(): MedPlan {
  return {
    drug: "药",
    per_day: 1,
    meal: "饭后",
    dosage: "一片",
    times: [],
    created_at: "2026-10-30 08:00",
  };
}
