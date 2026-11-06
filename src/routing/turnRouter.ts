import {
  END_SESSION_EXCLUDE_HINTS,
  END_SESSION_TONE_SUFFIXES,
  EXPLICIT_EXIT_CONTENT,
  FIXED_END_SESSION_PHRASES,
  FUZZY_END_SESSION_PHRASES,
  WAKE_WORD_CONTENTS,
} from "./phrases";

export type AsrRoute = "awake" | "exit" | "clear" | "upload_log" | "image" | "normal";

export interface TurnRouteInput {
  text: string;
  hasImage?: boolean;
}

export interface TurnRouter {
  route(input: TurnRouteInput): AsrRoute;
}

export class DefaultTurnRouter implements TurnRouter {
  route(input: TurnRouteInput): AsrRoute {
    return classifyAsr(input.text, input.hasImage === true);
  }
}

export function classifyAsr(text: string, hasImage = false): AsrRoute {
  const content = String(text || "");
  if ((WAKE_WORD_CONTENTS as readonly string[]).includes(content)) return "awake";
  if (content === EXPLICIT_EXIT_CONTENT || matchesEndSession(content)) return "exit";
  if (content.includes("清除") && content.includes("上下文")) return "clear";
  if (content.includes("上报日志") || content.includes("上传日志")) return "upload_log";
  if (hasImage) return "image";
  return "normal";
}

function matchesEndSession(content: string): boolean {
  const normalized = normalizeEndSessionContent(content);
  if (!normalized) return false;
  if (END_SESSION_EXCLUDE_HINTS.some((hint) => normalized.includes(hint))) return false;
  const stripped = stripToneSuffixes(normalized);
  if (FIXED_END_SESSION_PHRASES.some((phrase) => repeatedExactMatch(stripped, phrase))) return true;
  return FUZZY_END_SESSION_PHRASES.some((phrase) => stripped.includes(phrase));
}

function normalizeEndSessionContent(content: string): string {
  return content.normalize("NFKC").replace(new RegExp("[^\\p{L}\\p{N}]", "g"), "");
}

function stripToneSuffixes(value: string): string {
  let stripped = value;
  while (stripped.length > 1) {
    const suffix = END_SESSION_TONE_SUFFIXES.find((candidate) => stripped.endsWith(candidate));
    if (!suffix) break;
    stripped = stripped.slice(0, -suffix.length);
  }
  return stripped;
}

function repeatedExactMatch(value: string, phrase: string): boolean {
  if (value === phrase) return true;
  if (!value.startsWith(phrase) || value.length % phrase.length !== 0) return false;
  const repetitions = value.length / phrase.length;
  return repetitions >= 2 && phrase.repeat(repetitions) === value;
}
