import type { AgentChatMessage, ChatMessage } from "@listenai/agent-sdk";
import {
  truncateUtf8,
  utf8ByteLength,
} from "../text/utf8Budget";

export const MAX_HISTORY_FETCH_MESSAGES = 800;
const DEFAULT_FIELD_BYTES = 12 << 10;
const MAX_TOOL_CALLS_PER_MESSAGE = 20;
const MAX_TOOL_ARGUMENT_BYTES = 64 << 10;

export function selectRecentHistory(
  messages: ChatMessage[],
): AgentChatMessage[] {
  const normalized = expandLegacyToolHistory(messages.slice(-MAX_HISTORY_FETCH_MESSAGES))
    .map((message) => normalizeMessage(message, DEFAULT_FIELD_BYTES))
    .filter((message): message is AgentChatMessage => Boolean(message));
  const groups = groupByUserTurn(normalized)
    .map(removeIncompleteToolChains)
    .filter(isCompleteUserTurn);
  return flatten(groups);
}

export function projectHistoryForTextModel(
  messages: AgentChatMessage[],
): AgentChatMessage[] {
  return messages.map((message) => {
    if (!Array.isArray(message.content)) return message;
    return {
      ...message,
      content: structuredHistoryText(message.content),
    };
  });
}

function expandLegacyToolHistory(messages: ChatMessage[]): ChatMessage[] {
  const output: ChatMessage[] = [];
  for (const message of messages) {
    const meta = isRecord(message.meta) ? message.meta : undefined;
    if (message.role !== "assistant" || meta?.type !== "tool_call" || !Array.isArray(meta.data)) {
      output.push(message);
      continue;
    }
    const expanded = meta.data
      .map(readLegacyToolHistoryMessage)
      .filter((item): item is ChatMessage => Boolean(item));
    if (expanded.length > 0) output.push(...expanded);
    else output.push(message);
  }
  return output;
}

function structuredHistoryText(content: unknown[]): string {
  for (const item of content) {
    if (!isRecord(item) || item.type !== "text") continue;
    if (typeof item.text === "string") return item.text;
    if (typeof item.content === "string") return item.content;
  }
  return "";
}

function readLegacyToolHistoryMessage(value: unknown): ChatMessage | null {
  if (!isRecord(value) || typeof value.role !== "string") return null;
  const toolCallId = typeof value.tool_call_id === "string"
    ? value.tool_call_id
    : typeof value.toolCallId === "string"
      ? value.toolCallId
      : null;
  const toolCalls = Array.isArray(value.tool_calls)
    ? value.tool_calls
    : Array.isArray(value.toolCalls)
      ? value.toolCalls
      : undefined;
  const sourceMeta = isRecord(value.meta) ? value.meta : {};
  const meta = typeof value.name === "string"
    ? { ...sourceMeta, name: value.name }
    : sourceMeta;
  let content = value.content as ChatMessage["content"];
  if (value.role === "assistant" && Array.isArray(value.content)) {
    content = structuredHistoryText(value.content);
  }
  return {
    role: value.role,
    content,
    toolCallId,
    ...(toolCalls ? { toolCalls } : {}),
    ...(Object.keys(meta).length > 0 ? { meta } : {}),
  };
}

function flatten(groups: AgentChatMessage[][]): AgentChatMessage[] {
  const output: AgentChatMessage[] = [];
  for (const group of groups) output.push(...group);
  return output;
}

function groupByUserTurn(messages: AgentChatMessage[]): AgentChatMessage[][] {
  const groups: AgentChatMessage[][] = [];
  let current: AgentChatMessage[] | null = null;
  for (const message of messages) {
    if (message.role === "user") {
      current = [message];
      groups.push(current);
      continue;
    }
    if (current) current.push(message);
  }
  return groups;
}

function removeIncompleteToolChains(messages: AgentChatMessage[]): AgentChatMessage[] {
  const output: AgentChatMessage[] = [];
  for (let index = 0; index < messages.length; index += 1) {
    const message = messages[index];
    if (message.role === "assistant" && message.toolCalls?.length) {
      const expected = new Set(message.toolCalls.map((call) => call.id));
      const results: AgentChatMessage[] = [];
      let next = index + 1;
      while (next < messages.length && messages[next].role === "tool") {
        const result = messages[next];
        if (result.toolCallId && expected.has(result.toolCallId)) results.push(result);
        next += 1;
      }
      const resultIds = results.map((result) => result.toolCallId!);
      const complete = expected.size === message.toolCalls.length
        && resultIds.length === expected.size
        && new Set(resultIds).size === expected.size;
      if (complete) output.push(message, ...results);
      else if (message.content !== null && message.content !== "") {
        output.push({ ...message, toolCalls: undefined });
      }
      index = next - 1;
      continue;
    }
    if (message.role === "tool") continue;
    if (
      message.role === "assistant"
      && !message.toolCalls?.length
      && (message.content === null || message.content === "")
    ) {
      continue;
    }
    output.push(message);
  }
  return output;
}

function isCompleteUserTurn(messages: AgentChatMessage[]): boolean {
  if (messages.length === 0 || messages[0].role !== "user") return false;
  if (messages.slice(1).some((message) => message.role === "user")) return false;
  for (let index = 0; index < messages.length; index += 1) {
    const message = messages[index];
    if (message.role === "tool") return false;
    if (
      message.role === "assistant"
      && !message.toolCalls?.length
      && (message.content === null || message.content === "")
    ) {
      return false;
    }
    if (message.role !== "assistant" || !message.toolCalls?.length) continue;
    const expected = message.toolCalls.map((call) => call.id);
    const results = messages.slice(index + 1, index + 1 + expected.length);
    if (
      new Set(expected).size !== expected.length
      || results.length !== expected.length
      || results.some((result) => result.role !== "tool" || !result.toolCallId)
      || new Set(results.map((result) => result.toolCallId!)).size !== expected.length
      || results.some((result) => !expected.includes(result.toolCallId!))
    ) {
      return false;
    }
    index += results.length;
  }
  return true;
}

function normalizeMessage(message: ChatMessage, fieldBytes: number): AgentChatMessage | null {
  if (message.role !== "user" && message.role !== "assistant" && message.role !== "tool") return null;
  let rawContent = typeof message.content === "string"
    ? legacyImageHistoryText(message.content) ?? message.content
    : message.content;
  if (message.role === "assistant" && Array.isArray(message.content)) {
    rawContent = structuredHistoryText(message.content);
  }
  const content = normalizeContent(rawContent, fieldBytes);
  const toolCalls = normalizeToolCalls(message.toolCalls);
  const toolCallId = isSafeToolCallId(message.toolCallId)
    ? message.toolCallId
    : undefined;
  const meta = isRecord(message.meta) ? message.meta : {};
  const name = safeName(meta.name);
  return {
    role: message.role,
    content,
    ...(toolCallId ? { toolCallId } : {}),
    ...(toolCalls.length > 0 ? { toolCalls } : {}),
    ...(name ? { name } : {}),
  };
}

function legacyImageHistoryText(content: string): string | null {
  if (!content.startsWith("[")) return null;
  let parsed: unknown;
  try {
    parsed = JSON.parse(content);
  } catch {
    return null;
  }
  if (!Array.isArray(parsed) || !parsed.some((item) => (
    isRecord(item)
    && item.type === "image_base64"
    && typeof item.content === "string"
  ))) return null;
  for (const item of parsed) {
    if (!isRecord(item) || item.type !== "text") continue;
    if (typeof item.text === "string") return item.text;
    if (typeof item.content === "string") return item.content;
  }
  return "";
}

function normalizeContent(value: unknown, fieldBytes: number): AgentChatMessage["content"] {
  if (typeof value === "string") return truncateUtf8(value, fieldBytes);
  if (value === null || value === undefined) return null;
  if (!Array.isArray(value)) return "";
  const output: Array<Record<string, unknown>> = [];
  for (const raw of value.slice(0, 16)) {
    if (!isRecord(raw)) continue;
    if (raw.type === "text" && typeof raw.text === "string") {
      output.push({ type: "text", text: truncateUtf8(raw.text, fieldBytes) });
      continue;
    }
    const image = isRecord(raw.image_url) ? raw.image_url : {};
    if (raw.type === "image_url" && typeof image.url === "string") {
      output.push({ type: "image_url", image_url: { url: truncateUtf8(image.url, 4_096) } });
    }
  }
  return output;
}

function normalizeToolCalls(value: unknown): NonNullable<AgentChatMessage["toolCalls"]> {
  if (!Array.isArray(value)) return [];
  const output: NonNullable<AgentChatMessage["toolCalls"]> = [];
  for (const raw of value.slice(0, MAX_TOOL_CALLS_PER_MESSAGE)) {
    if (!isRecord(raw) || !isSafeToolCallId(raw.id)) continue;
    const fn = isRecord(raw.function) ? raw.function : raw;
    const name = safeName(fn.name);
    const args = typeof fn.arguments === "string" ? fn.arguments : "";
    if (!name || utf8ByteLength(args) > MAX_TOOL_ARGUMENT_BYTES) continue;
    output.push({
      id: raw.id,
      type: "function",
      function: { name, arguments: args },
    });
  }
  return output;
}

function isSafeToolCallId(value: unknown): value is string {
  return typeof value === "string" && /^[A-Za-z0-9._:-]{1,128}$/.test(value);
}

function safeName(value: unknown): string {
  return typeof value === "string" && /^[A-Za-z_][A-Za-z0-9_-]{0,63}$/.test(value)
    ? value
    : "";
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}
