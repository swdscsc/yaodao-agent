import { AgentError } from "@listenai/agent-sdk";
import { utf8ByteLength } from "../text/utf8Budget";

export interface ContentMeta {
  emotion?: string;
  language?: string;
}

export interface ParsedSegment {
  text: string;
  meta: ContentMeta;
}

export interface ContentParseResult {
  segments: ParsedSegment[];
  ignoreSession: boolean;
  endSession: boolean;
}

export interface ContentTagParserOptions {
  maxPendingBytes?: number;
  /** @deprecated Use maxPendingBytes. */
  maxPendingChars?: number;
}

export class ContentTagParser {
  private buffer = "";
  private emotion?: string;
  private language?: string;
  private ignoreSession = false;
  private endSession = false;
  private readonly maxPendingBytes: number;

  constructor(options: ContentTagParserOptions = {}) {
    this.maxPendingBytes = Math.max(
      8,
      Math.min(options.maxPendingBytes ?? options.maxPendingChars ?? 4_096, 16_384),
    );
  }

  /** Accepts complete decoded JavaScript strings; byte framing is owned by the SDK UTF-8 decoder. */
  push(chunk: string): ContentParseResult {
    this.buffer += chunk;
    return this.drain(false);
  }

  finish(): ContentParseResult {
    return this.drain(true);
  }

  discardPending(): ContentParseResult {
    this.buffer = "";
    return {
      segments: [],
      ignoreSession: this.ignoreSession,
      endSession: this.endSession,
    };
  }

  private drain(final: boolean): ContentParseResult {
    const segments: ParsedSegment[] = [];
    while (this.buffer) {
      const special = findSpecialStart(this.buffer);
      if (special > 0) {
        this.emit(segments, this.buffer.slice(0, special));
        this.buffer = this.buffer.slice(special);
        continue;
      }
      if (special < 0) {
        this.emit(segments, this.buffer);
        this.buffer = "";
        break;
      }
      if (this.buffer.startsWith("（")) {
        const end = this.buffer.indexOf("）", 1);
        if (end < 0) {
          if (final) this.buffer = "";
          else this.assertPendingBound();
          break;
        }
        this.buffer = this.buffer.slice(end + 1);
        continue;
      }
      if (this.buffer.startsWith("[")
        && this.buffer.length < 2) {
        if (final) this.buffer = "";
        else this.assertPendingBound();
        break;
      }
      if (this.buffer.startsWith("[")
        && this.buffer[1] !== "#"
        && this.buffer[1] !== "$") {
        this.emit(segments, "[");
        this.buffer = this.buffer.slice(1);
        continue;
      }
      if (this.buffer.startsWith("[#") || this.buffer.startsWith("[$")) {
        const end = this.buffer.indexOf("]", 2);
        if (end < 0) {
          if (final) {
            this.buffer = "";
          } else this.assertPendingBound();
          break;
        }
        const token = this.buffer.slice(2, end).trim();
        if (!token) {
          this.emit(segments, this.buffer.slice(0, end + 1));
        } else if (this.buffer[1] === "#") {
          if (!this.language) this.emotion = token;
        } else {
          this.language = token;
        }
        this.buffer = this.buffer.slice(end + 1);
        continue;
      }
      const control = matchControl(this.buffer);
      if (control === "partial" && !final) break;
      if (control === "partial" && final) {
        this.buffer = "";
        break;
      }
      if (control === "ignore") {
        this.ignoreSession = true;
        this.buffer = this.buffer.slice("<IGNORE_SESSION>".length);
        continue;
      }
      if (control === "end") {
        this.endSession = true;
        this.buffer = this.buffer.slice("<END_SESSION>".length);
        continue;
      }
      this.emit(segments, this.buffer[0]);
      this.buffer = this.buffer.slice(1);
    }
    return {
      segments,
      ignoreSession: this.ignoreSession,
      endSession: this.endSession,
    };
  }

  private assertPendingBound(): void {
    if (utf8ByteLength(this.buffer) <= this.maxPendingBytes) return;
    this.buffer = "";
    throw new AgentError("AGENT_RESPONSE_PROTOCOL_ERROR", "Response tag exceeds the pending limit", {
      phase: "response",
    });
  }

  private emit(segments: ParsedSegment[], text: string): void {
    if (!text) return;
    const meta: ContentMeta = {
      ...(this.emotion ? { emotion: this.emotion } : {}),
      ...(this.language ? { language: this.language } : {}),
    };
    const previous = segments[segments.length - 1];
    if (previous && sameMeta(previous.meta, meta)) previous.text += text;
    else segments.push({ text, meta });
  }
}

export function parseContentChunks(chunks: string[]): {
  text: string;
  emotion?: string;
  language?: string;
  ignoreSession: boolean;
  endSession: boolean;
} {
  const parser = new ContentTagParser();
  let text = "";
  let emotion: string | undefined;
  let language: string | undefined;
  let result: ContentParseResult = { segments: [], ignoreSession: false, endSession: false };
  for (const chunk of chunks) {
    result = parser.push(chunk);
    for (const segment of result.segments) {
      text += segment.text;
      emotion = segment.meta.emotion ?? emotion;
      language = segment.meta.language ?? language;
    }
  }
  result = parser.finish();
  for (const segment of result.segments) {
    text += segment.text;
    emotion = segment.meta.emotion ?? emotion;
    language = segment.meta.language ?? language;
  }
  return {
    text,
    ...(emotion ? { emotion } : {}),
    ...(language ? { language } : {}),
    ignoreSession: result.ignoreSession,
    endSession: result.endSession,
  };
}

function findSpecialStart(value: string): number {
  const candidates = [value.indexOf("["), value.indexOf("<"), value.indexOf("（")]
    .filter((index) => index >= 0);
  return candidates.length > 0 ? Math.min(...candidates) : -1;
}

function matchControl(value: string): "ignore" | "end" | "partial" | "none" {
  if (value.startsWith("<IGNORE_SESSION>")) return "ignore";
  if (value.startsWith("<END_SESSION>")) return "end";
  if ("<IGNORE_SESSION>".startsWith(value) || "<END_SESSION>".startsWith(value)) return "partial";
  return "none";
}

function sameMeta(left: ContentMeta, right: ContentMeta): boolean {
  return left.emotion === right.emotion && left.language === right.language;
}
