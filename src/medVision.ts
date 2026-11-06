// 药品照片识别：把视觉模型的原始输出解析成结构化「草稿」，并驱动「多步确认」流程。
//
// 设计原则（适老化 + 安全）：
// - 识别只是辅助，绝不替用户臆测药量或疗程；认不清就如实说「没看清」，让用户口述补充。
// - 一次只确认一个缺失项，确认齐了才落库。
// - 本文件是纯逻辑，不依赖运行环境（host / 模型），便于单元测试（用 mock 视觉输出来测）。

export type DraftField = "drug" | "per_day" | "meal" | "dosage" | "times";

export interface MedicineDraft {
  drug?: string;
  per_day?: number;
  meal?: string;
  dosage?: string;
  times?: string[];
  /** 视觉模型原始描述，便于兜底与调试 */
  raw_text: string;
  /** 是否识别出药品（false 时降级为人工口述建档） */
  is_medicine: boolean;
}

export const MEAL_VALUES = ["饭前", "饭后", "空腹", "随时"] as const;

/** 给视觉模型的系统提示词：要求它只输出紧凑 JSON，不啰嗦。 */
export const MEDICINE_VISION_PROMPT = [
  "你是一台「药品包装识别器」，专门从照片里读出用药信息。",
  "请只输出一个 JSON 对象，不要任何解释、不要 markdown 代码块，字段如下：",
  "{\n  \"is_medicine\": true|false,\n  \"drug\": \"药名，如 阿莫西林胶囊 / 硝苯地平控释片\",\n  \"per_day\": 每天服用次数(数字),\n  \"meal\": \"饭前|饭后|空腹|随时 之一，看不出就填空字符串\",\n  \"dosage\": \"每次剂量，如 2粒 / 1片 / 5毫升\",\n  \"times\": [\"08:00\",\"14:00\"](具体时间点，看不出就空数组),\n  \"note\": \"盒身/说明书上看到的原话，如 口服一次2粒一日3次\n}",
  "规则：",
  "1. 只在确定时填值；不确定就留空字符串或空数组，宁可少填也不要瞎猜。",
  "2. 剂量不要换算，照原样读（如「一次2粒」就写 2粒）。",
  "3. 如果照片里不是药品（如家具、人、风景），is_medicine 写 false，其它留空。",
].join("\n");

const CN_NUM: Record<string, string> = {
  零: "0", 一: "1", 二: "2", 两: "2", 三: "3", 四: "4",
  五: "5", 六: "6", 七: "7", 八: "8", 九: "9", 十: "10",
};

function cnToNum(raw: string): number | undefined {
  const s = raw.trim();
  if (/^\d+$/.test(s)) return Number(s);
  if (CN_NUM[s]) return Number(CN_NUM[s]);
  if (s === "十") return 10;
  // 处理「十二」「二十」这类（简单覆盖常见情况）
  const m = /^(十)?([0-9一二三四五六七八九两])?(十)([0-9一二三四五六七八九两])?$/.exec(s);
  if (m) {
    const tens = m[1] ? 10 : m[2] ? Number(CN_NUM[m[2]]) * 10 : 10;
    const ones = m[4] ? Number(CN_NUM[m[4]]) : 0;
    return tens + ones;
  }
  return undefined;
}

function normalizeMeal(text: string): string | undefined {
  if (/随时/.test(text)) return "随时";
  if (/空腹/.test(text)) return "空腹";
  if (/(饭前|餐前)/.test(text)) return "饭前";
  if (/(饭后|餐后)/.test(text)) return "饭后";
  if (/(饭|餐)/.test(text)) return "饭后"; // 只说「吃饭时」默认饭后，确认环节会再问
  return undefined;
}

function normalizeTimes(values: unknown): string[] {
  const out: string[] = [];
  const list = Array.isArray(values) ? values : [];
  for (const v of list) {
    const s = String(v).trim();
    const m = /^(\d{1,2})[:：](\d{2})$/.exec(s);
    if (m) {
      const hh = m[1].padStart(2, "0");
      const mm = m[2];
      out.push(`${hh}:${mm}`);
    }
  }
  return out;
}

/**
 * 解析视觉模型输出：优先解析 JSON；失败则用正则尽力从文本抽取。
 * 任何异常都降级为「未识别」，绝不让流程崩溃。
 */
export function parseVisionOutput(raw: string): MedicineDraft {
  const text = (raw || "").trim();
  const base: MedicineDraft = { raw_text: text, is_medicine: false };

  // 1) 抽取第一个 JSON 对象
  const open = text.indexOf("{");
  const close = text.lastIndexOf("}");
  if (open >= 0 && close > open) {
    try {
      const obj = JSON.parse(text.slice(open, close + 1)) as Record<string, unknown>;
      const isMed = obj.is_medicine === true || typeof obj.drug === "string" && obj.drug.length > 0;
      if (!isMed) return { ...base, is_medicine: false };
      const perDay = cnToNum(String(obj.per_day ?? ""));
      return {
        raw_text: text,
        is_medicine: true,
        drug: typeof obj.drug === "string" && obj.drug.trim() ? obj.drug.trim() : undefined,
        per_day: Number.isFinite(perDay) && (perDay as number) > 0 ? (perDay as number) : undefined,
        meal: typeof obj.meal === "string" ? normalizeMeal(obj.meal) : undefined,
        dosage: typeof obj.dosage === "string" && obj.dosage.trim() ? obj.dosage.trim() : undefined,
        times: normalizeTimes(obj.times),
      };
    } catch {
      // 落到文本兜底
    }
  }

  // 2) 文本兜底：尽力识别（避开裸"药"字，因为"不是药"也会含"药"）
  const hasMedKeyword =
    /片|粒|胶囊|口服|冲剂|滴剂|贴剂|mg|ml|g\b|剂量|处方|适应症|用法用量|一日|每日/.test(text)
    && !/不是药|没有药|哪种药|什么药|药吗|药呢/.test(text);
  if (!hasMedKeyword) return base;
  const per = /(一日|每天|一天)\s*([0-9一二三四五六七八九十两]+)\s*次/.exec(text);
  const perDay = per ? cnToNum(per[2]) : undefined;
  const dose = /一次\s*([0-9一二三四五六七八九十两]+)\s*([片粒袋支丸颗贴mg克g毫升ml]+)/.exec(text);
  const times: string[] = [];
  const re = /(\d{1,2})[:：](\d{2})/g;
  let mm: RegExpExecArray | null;
  while ((mm = re.exec(text)) !== null) times.push(`${mm[1].padStart(2, "0")}:${mm[2]}`);
  const meal = /(饭后|餐后)/.test(text)
    ? "饭后"
    : /(饭前|餐前)/.test(text)
      ? "饭前"
      : /空腹/.test(text)
        ? "空腹"
        : /随时/.test(text)
          ? "随时"
          : undefined;
  return {
    raw_text: text,
    is_medicine: true,
    per_day: Number.isFinite(perDay as number) && (perDay as number) > 0 ? (perDay as number) : undefined,
    meal,
    dosage: dose ? `${dose[1]}${dose[2]}` : undefined,
    times,
  };
}

/** 还缺哪些必填项（times 不强制，缺了也会在确认时顺带问）。 */
export function missingFields(d: MedicineDraft): DraftField[] {
  const missing: DraftField[] = [];
  if (!d.drug) missing.push("drug");
  if (d.per_day == null || d.per_day <= 0) missing.push("per_day");
  if (!d.meal) missing.push("meal");
  if (!d.dosage) missing.push("dosage");
  return missing;
}

const QUESTIONS: Record<DraftField, string> = {
  drug: "这盒药叫什么名字呀？您看盒子上有没有药名，念给我听就行。",
  per_day: "它每天要吃几次呢？",
  meal: "是饭前吃还是饭后吃呀？",
  dosage: "一次吃多少？比如一片还是两粒？",
  times: "大概几点吃？说不上具体时间也没关系，我帮您记个大概。",
};

/** 下一步该问什么（一次只问一个，适老化）。全部齐了返回空串。 */
export function nextQuestion(d: MedicineDraft): string {
  const missing = missingFields(d);
  return missing.length > 0 ? QUESTIONS[missing[0]] : "";
}

/** 已识别内容的口语化摘要，用于念给用户听。 */
export function draftSummary(d: MedicineDraft): string {
  if (!d.is_medicine) return "这张照片里我没认出是哪种药。";
  const parts: string[] = [];
  if (d.drug) parts.push(`这盒药大概是【${d.drug}】`);
  else parts.push("这盒药名字我没看清");
  if (d.per_day) parts.push(`一天 ${d.per_day} 次`);
  if (d.meal) parts.push(`${d.meal}吃`);
  if (d.dosage) parts.push(`一次 ${d.dosage}`);
  if (d.times && d.times.length) parts.push(`时间大概是 ${d.times.join("、")}`);
  return parts.join("，") + (parts.length ? "。" : "");
}

export function isComplete(d: MedicineDraft): boolean {
  return missingFields(d).length === 0;
}

/** 写入对话历史的易读标记，让后续 ReAct 轮次能接着确认缺失项。 */
export function draftToHistoryMarker(d: MedicineDraft): string {
  if (!d.is_medicine) return "【用药照片识别】未识别出药品，转为用户口述建档。";
  const missing = missingFields(d);
  const detail = [
    d.drug ? `药名=${d.drug}` : "药名=?",
    d.per_day ? `每天${d.per_day}次` : "每天?次",
    d.meal ? `${d.meal}吃` : "餐次=?",
    d.dosage ? `一次${d.dosage}` : "剂量=?",
    d.times && d.times.length ? `时间=${d.times.join("/")}` : "时间=?",
  ].join("；");
  return `【用药照片识别】${detail}。待确认：${missing.length ? missing.join("、") : "无"}`;
}

/** 没认出药品时的兜底话术。 */
export function noMedicineAnswer(): string {
  return "这张照片我没能认出是哪种药。没关系，您直接告诉我药名，还有每天吃几次、饭前饭后、一次吃多少，我帮您记上就行。";
}
