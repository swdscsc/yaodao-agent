import type { AgentChatMessage as ChatMessage } from "@listenai/agent-sdk";
import { DEFAULT_WAKE_WORD, OFFICIAL_SYSTEM_PROMPT, PROMPT_SECTION_LABELS } from "./prompts";
import {
  MAX_CURRENT_USER_TEXT_BYTES,
  boundedCurrentUserText,
  truncateUtf8,
  utf8ByteLength,
} from "../text/utf8Budget";

export const MAX_SYSTEM_PROMPT_BYTES = 128 << 10;
export const MAX_USER_INPUT_BYTES = MAX_CURRENT_USER_TEXT_BYTES;

export interface PromptBuildInput {
  explicitSystemPrompt?: string;
  configuredSystemPrompt?: string;
  platformSystemPrompt?: string;
  basePrompt?: string;
  persona?: string;
  portrait?: string;
  userName?: string;
  city?: string;
  memory?: string;
  knowledge?: string;
  dsaSystemPrompt?: string;
  currentTime?: string;
  emotion?: string;
  wakeWord?: string;
  history?: ChatMessage[];
  userText?: string;
}

export interface PromptBuilder {
  build(input: PromptBuildInput): ChatMessage[];
}

export class DefaultPromptBuilder implements PromptBuilder {
  build(input: PromptBuildInput): ChatMessage[] {
    const system = buildSystemPrompt({
      ...input,
      basePrompt: selectBaseSystemPrompt(
        input.explicitSystemPrompt,
        input.configuredSystemPrompt,
        input.platformSystemPrompt,
      ),
    });
    const history = (input.history ?? []).map((message) => ({ ...message }));
    return [
      { role: "system", content: system },
      ...history,
      { role: "user", content: boundedCurrentUserText(input.userText ?? "") },
    ];
  }
}

export function selectBaseSystemPrompt(
  explicit?: string,
  configured?: string,
  platform?: string,
): string {
  return firstNonEmpty(explicit, configured, platform, OFFICIAL_SYSTEM_PROMPT);
}

export function buildSystemPrompt(input: PromptBuildInput): string {
  const template = firstNonEmpty(input.basePrompt, OFFICIAL_SYSTEM_PROMPT);
  const renderedBase = renderLegacyVariables(template, input);
  const sections: string[] = [truncateUtf8(renderedBase, 64 << 10)];
  const missingRole = [
    hasTemplateVariable(template, "persona") ? undefined : input.persona,
    hasTemplateVariable(template, "role_portrait") ? undefined : input.portrait,
  ].filter(nonEmpty).join("\n");
  appendSection(sections, PROMPT_SECTION_LABELS.role, missingRole, 16 << 10);
  if (!hasTemplateVariable(template, "user_info")) {
    appendSection(sections, PROMPT_SECTION_LABELS.user, input.userName, 4 << 10);
  }
  if (!hasTemplateVariable(template, "city") && !hasTemplateVariable(template, "location")) {
    appendSection(sections, PROMPT_SECTION_LABELS.location, input.city, 1 << 10);
  }
  appendSection(sections, PROMPT_SECTION_LABELS.memory, input.memory, 32 << 10);
  appendSection(sections, PROMPT_SECTION_LABELS.knowledge, input.knowledge, 12 << 10);
  appendSection(sections, PROMPT_SECTION_LABELS.dsa, input.dsaSystemPrompt, 64 << 10);
  appendSection(
    sections,
    PROMPT_SECTION_LABELS.wakeWord,
    firstNonEmpty(input.wakeWord, DEFAULT_WAKE_WORD),
    1 << 10,
  );
  return fitSections(sections);
}

function appendSection(sections: string[], label: string, content: string | undefined, maximumBytes: number): void {
  const value = typeof content === "string" ? content.trim() : "";
  if (value) sections.push(`## ${label}\n${truncateUtf8(value, maximumBytes)}`);
}

function fitSections(sections: string[]): string {
  let output = "";
  let usedBytes = 0;
  for (const section of sections) {
    const prefix = output ? "\n\n" : "";
    const prefixBytes = prefix.length;
    const remaining = MAX_SYSTEM_PROMPT_BYTES - usedBytes;
    if (remaining <= prefixBytes) break;
    const sectionBytes = utf8ByteLength(section);
    if (prefixBytes + sectionBytes <= remaining) {
      output += prefix + section;
      usedBytes += prefixBytes + sectionBytes;
      continue;
    }
    const fitted = truncateUtf8(section, remaining - prefixBytes);
    output += prefix + fitted;
    usedBytes += prefixBytes + utf8ByteLength(fitted);
  }
  return output;
}

function renderLegacyVariables(template: string, input: PromptBuildInput): string {
  const values: Record<string, string> = {
    persona: input.persona?.trim() ?? "",
    role_portrait: input.portrait?.trim() ?? "",
    city: input.city?.trim() ?? "",
    location: input.city?.trim() ?? "",
    current_time: input.currentTime ?? formatCurrentTime(),
    user_info: input.userName
      ? `\n* 用户名称：\n- ${input.userName.trim()}\n`
      : "当前没有任何用户信息",
    emotion: input.emotion?.trim() ?? "",
  };
  return template.replace(
    /{{{?\s*(persona|role_portrait|city|location|current_time|user_info|emotion)\s*}?}}/g,
    (_match, name: string) => values[name] ?? "",
  );
}

function hasTemplateVariable(template: string, name: string): boolean {
  return new RegExp(`{{{?\\s*${name}\\s*}?}}`).test(template);
}

function formatCurrentTime(): string {
  const value = new Date(Date.now() + 8 * 60 * 60 * 1_000).toISOString();
  return value.slice(0, 19).replace("T", " ");
}

function firstNonEmpty(...values: Array<string | undefined>): string {
  return values.find(nonEmpty)?.trim() ?? "";
}

function nonEmpty(value: string | undefined): value is string {
  return typeof value === "string" && value.trim().length > 0;
}
