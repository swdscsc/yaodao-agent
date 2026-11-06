import { test } from "node:test";
import assert from "node:assert/strict";
import {
  MEDICINE_VISION_PROMPT,
  draftSummary,
  draftToHistoryMarker,
  isComplete,
  missingFields,
  nextQuestion,
  noMedicineAnswer,
  parseVisionOutput,
  type DraftField,
  type MedicineDraft,
} from "../src/medVision";

function completeDraft(): MedicineDraft {
  return {
    is_medicine: true,
    drug: "阿莫西林胶囊",
    per_day: 3,
    meal: "饭后",
    dosage: "2粒",
    times: ["08:00", "14:00", "20:00"],
    raw_text: "",
  };
}

test("视觉模型返回 JSON：完整解析", () => {
  const json = JSON.stringify({
    is_medicine: true,
    drug: "硝苯地平控释片",
    per_day: 1,
    meal: "饭后",
    dosage: "1片",
    times: ["08:00"],
    note: "口服一次1片一日1次",
  });
  const d = parseVisionOutput(`好的，识别结果如下：\n${json}`);
  assert.equal(d.is_medicine, true);
  assert.equal(d.drug, "硝苯地平控释片");
  assert.equal(d.per_day, 1);
  assert.equal(d.meal, "饭后");
  assert.equal(d.dosage, "1片");
  assert.deepEqual(d.times, ["08:00"]);
});

test("视觉模型输出带 markdown 代码块也能解析", () => {
  const json = '```json\n{\n  "is_medicine": true,\n  "drug": "维生素C",\n  "per_day": 2,\n  "meal": "随时",\n  "dosage": "1片"\n}\n```';
  const d = parseVisionOutput(json);
  assert.equal(d.drug, "维生素C");
  assert.equal(d.per_day, 2);
  assert.equal(d.meal, "随时");
});

test("JSON 里字段缺失时回填为空，不臆测", () => {
  const d = parseVisionOutput(JSON.stringify({ is_medicine: true, drug: "布洛芬" }));
  assert.equal(d.is_medicine, true);
  assert.equal(d.drug, "布洛芬");
  assert.equal(d.per_day, undefined);
  assert.equal(d.meal, undefined);
  assert.equal(d.dosage, undefined);
});

test("纯文本兜底：从说明文字抽取次数/剂量/时间", () => {
  const text = "盒身写：口服，一次两粒，一日三次，早中晚饭后服用。";
  const d = parseVisionOutput(text);
  assert.equal(d.is_medicine, true);
  assert.equal(d.per_day, 3);
  assert.equal(d.dosage, "两粒");
  assert.equal(d.meal, "饭后");
});

test("非药品照片：is_medicine=false，转口述建档", () => {
  const d = parseVisionOutput("这是一张客厅的沙发照片，不是药。");
  assert.equal(d.is_medicine, false);
  assert.equal(noMedicineAnswer().includes("没能认出"), true);
});

test("缺字段 / 多步确认顺序", () => {
  const d: MedicineDraft = {
    is_medicine: true,
    drug: "阿莫西林",
    // per_day / meal / dosage 都缺
    raw_text: "",
  };
  const order: DraftField[] = [];
  let cur: MedicineDraft = { ...d };
  // 模拟逐轮补齐：每次问下一个缺失项，补齐后再问
  while (!isComplete(cur)) {
    const q = nextQuestion(cur);
    assert.ok(q.length > 0, "还有缺失项时应有确认问题");
    const next = missingFields(cur)[0];
    order.push(next);
    if (next === "per_day") cur = { ...cur, per_day: 3 };
    else if (next === "meal") cur = { ...cur, meal: "饭后" };
    else if (next === "dosage") cur = { ...cur, dosage: "2粒" };
    else if (next === "drug") cur = { ...cur, drug: "阿莫西林" };
    else if (next === "times") cur = { ...cur, times: ["08:00"] };
  }
  assert.deepEqual(order, ["per_day", "meal", "dosage"]);
  assert.equal(isComplete(cur), true);
});

test("draftSummary 口语化摘要", () => {
  const s = draftSummary(completeDraft());
  assert.ok(s.includes("阿莫西林胶囊"), "应念出药名");
  assert.ok(s.includes("一天 3 次"), "应念出频次");
  assert.ok(s.includes("饭后吃"), "应念出餐次");
  assert.ok(s.includes("一次 2粒"), "应念出剂量");
});

test("draftToHistoryMarker 让后续轮次能接着确认", () => {
  const marker = draftToHistoryMarker({
    is_medicine: true,
    drug: "阿莫西林",
    per_day: 3,
    raw_text: "",
  });
  assert.ok(marker.includes("【用药照片识别】"), "标记前缀");
  assert.ok(marker.includes("待确认"), "应标注待确认项");
  assert.ok(marker.includes("meal") || marker.includes("餐次"), "应指出缺餐次");
});

test("MEDICINE_VISION_PROMPT 要求结构化 JSON 输出", () => {
  assert.ok(MEDICINE_VISION_PROMPT.includes("JSON"), "提示词应要求 JSON");
  assert.ok(MEDICINE_VISION_PROMPT.includes("is_medicine"), "提示词应说明字段");
});
