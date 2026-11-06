import {
  emitNLPFinish,
  emitRaw,
  emitTextStreamUrl,
  emitTTSStreamUrl,
  ensureTextStream,
  ensureTTSStream,
  log,
  type AgentEvent,
  type TextStream,
  type TTSStream,
} from "@listenai/agent-sdk";
import {
  buildEndSessionFrame,
  buildImageArtifactFrame,
} from "../tools/deviceFrameAdapter";
import {
  mapToolImageArtifacts,
  type ImageArtifact,
} from "../image/imageArtifacts";
import {
  ContentTagParser,
  type ContentMeta,
  type ContentParseResult,
} from "./contentTagParser";
import { safeErrorFields, safeLogUrl } from "../errors/safeLogging";
import { truncateUtf8, utf8ByteLength } from "../text/utf8Budget";

export const MAX_VISIBLE_ANSWER_BYTES = 128 << 10;

const AGENT_STOP_TEXT_SKIP_TOOLS = new Set(["take_photo"]);

function runBestEffort(steps: Array<() => void>): void {
  let firstError: unknown;
  let failed = false;
  for (const step of steps) {
    try {
      step();
    } catch (error) {
      if (!failed) {
        failed = true;
        firstError = error;
      }
    }
  }
  if (failed) throw firstError;
}

export interface ResponsePipeline {
  readonly finalAnswer: string;
  readonly ignoreSession: boolean;
  readonly endSession: boolean;
  readonly imageArtifacts: ImageArtifact[];
  readonly outputMeta: ContentMeta;
  readonly hasActivity: boolean;
  start(): void;
  write(text: string): void;
  handleEvent(event: AgentEvent): void;
  emitFrames(frames: unknown[]): void;
  flush(): void;
  discardPending(): void;
  abort(emitFinish?: boolean): void;
  finish(extraFrames?: unknown[]): void;
}

export interface ResponsePipelineProvider {
  create(sessionId: string): ResponsePipeline;
}

export class DefaultResponsePipelineProvider implements ResponsePipelineProvider {
  create(sessionId: string): ResponsePipeline {
    return new DeviceResponsePipeline(sessionId);
  }
}

export class DeviceResponsePipeline implements ResponsePipeline {
  private readonly parser = new ContentTagParser();
  private tts: TTSStream | null = null;
  private textStream: TextStream | null = null;
  private started = false;
  private closed = false;
  private finished = false;
  private visibleAnswer = "";
  private ignored = false;
  private endsSession = false;
  private readonly images: ImageArtifact[] = [];
  private meta: ContentMeta = {};
  private activity = false;

  constructor(private readonly sessionId: string) {}

  get finalAnswer(): string {
    return this.visibleAnswer;
  }

  get ignoreSession(): boolean {
    return this.ignored;
  }

  get endSession(): boolean {
    return this.endsSession;
  }

  get imageArtifacts(): ImageArtifact[] {
    return this.images.map((artifact) => ({ ...artifact }));
  }

  get outputMeta(): ContentMeta {
    return { ...this.meta };
  }

  get hasActivity(): boolean {
    return this.activity;
  }

  start(): void {
    if (this.started || this.finished) return;
    const startedAt = Date.now();
    const ttsStartedAt = Date.now();
    const tts = this.openTTS();
    const ttsOpenDurationMs = Date.now() - ttsStartedAt;
    const textStartedAt = Date.now();
    const textStream = this.openText();
    const textOpenDurationMs = Date.now() - textStartedAt;
    try {
      runBestEffort([
        () => { if (tts) emitTTSStreamUrl(this.sessionId, tts.url); },
        () => { if (textStream) emitTextStreamUrl(this.sessionId, textStream.url); },
      ]);
    } catch (error) {
      this.closed = true;
      try {
        runBestEffort([
          () => tts?.close(),
          () => textStream?.close(),
        ]);
      } catch {
        // Preserve the URL publication error while still attempting both closes.
      }
      throw error;
    }
    this.tts = tts;
    this.textStream = textStream;
    this.started = true;
    this.safeLogInfo("official voice response streams opened", {
      event: "response.streams_opened",
      sessionId: this.sessionId,
      durationMs: Date.now() - startedAt,
      ttsOpenDurationMs,
      textOpenDurationMs,
      ttsAvailable: Boolean(tts),
      textAvailable: Boolean(textStream),
      ...(tts ? { ttsUrl: safeLogUrl(tts.url) } : {}),
      ...(textStream ? { textStreamUrl: safeLogUrl(textStream.url) } : {}),
    });
  }

  write(text: string): void {
    if (this.finished || !text) return;
    this.start();
    this.consume(this.parser.push(text));
  }

  handleEvent(event: AgentEvent): void {
    if (this.finished) return;
    if (event.type === "output.delta") {
      if (event.meta) this.meta = { ...this.meta, ...event.meta };
      this.write(event.text);
      return;
    }
    if (event.type === "tool.started") {
      this.activity = true;
      return;
    }
    if (event.type === "tool.completed") {
      const artifacts = mapToolImageArtifacts(event.call.name, event.result);
      this.images.push(...artifacts);
      artifacts.forEach((artifact, index) => {
        if (artifact.kind !== "generated" && artifact.kind !== "edited") return;
        const frame = buildImageArtifactFrame(artifact, event.call.id, index);
        if (frame) emitRaw(this.sessionId, frame);
      });
      if (event.result.control.agentStop && !AGENT_STOP_TEXT_SKIP_TOOLS.has(event.call.name)) {
        const agentStopText = event.result.content.find(
          (item) => item.type === "text" && Boolean(item.text),
        );
        if (agentStopText?.type === "text") this.write(agentStopText.text);
      }
      return;
    }
  }

  emitFrames(frames: unknown[]): void {
    if (this.finished) return;
    for (const frame of frames) emitRaw(this.sessionId, frame as object);
  }

  flush(): void {
    if (this.finished) return;
    this.consume(this.parser.finish());
  }

  discardPending(): void {
    if (this.finished) return;
    this.consume(this.parser.discardPending());
  }

  abort(emitFinish = false): void {
    if (this.finished) return;
    runBestEffort([
      () => this.discardPending(),
      () => { this.finished = true; },
      () => this.closeStreams(),
      () => { if (emitFinish) emitNLPFinish(this.sessionId); },
    ]);
  }

  finish(extraFrames: unknown[] = []): void {
    if (this.finished) return;
    runBestEffort([
      () => { if (this.started) this.flush(); },
      () => { this.finished = true; },
      () => this.closeStreams(),
      ...extraFrames.map((frame) => () => emitRaw(this.sessionId, frame as object)),
      () => { if (this.endsSession) emitRaw(this.sessionId, buildEndSessionFrame()); },
      () => emitNLPFinish(this.sessionId),
    ]);
    this.safeLogInfo("official voice response finished", {
      event: "response.completed",
      sessionId: this.sessionId,
      answerBytes: utf8ByteLength(this.visibleAnswer),
      hasActivity: this.activity,
      imageCount: this.images.length,
      ignoreSession: this.ignored,
      endSession: this.endsSession,
    });
  }

  private safeLogInfo(message: string, fields: Record<string, unknown>): void {
    try {
      log.info(message, fields);
    } catch {
      // Logging must not change response stream behavior in lightweight hosts.
    }
  }

  private consume(result: ContentParseResult): void {
    this.ignored = result.ignoreSession;
    this.endsSession = result.endSession;
    for (const segment of result.segments) {
      if (!segment.text) continue;
      const remaining = MAX_VISIBLE_ANSWER_BYTES - utf8ByteLength(this.visibleAnswer);
      if (remaining <= 0) continue;
      const visible = truncateUtf8(segment.text, remaining);
      if (!visible) continue;
      this.activity = true;
      this.meta = { ...this.meta, ...segment.meta };
      this.visibleAnswer += visible;
      runBestEffort([
        () => this.tts?.send(visible),
        () => this.textStream?.send(visible),
      ]);
    }
  }

  private closeStreams(): void {
    if (this.closed) return;
    this.closed = true;
    runBestEffort([
      () => this.tts?.close(),
      () => this.textStream?.close(),
    ]);
  }

  private openTTS(): TTSStream | null {
    try {
      return ensureTTSStream({ provider: "listenai" });
    } catch (error) {
      log.warn("tts stream unavailable", safeErrorFields(error));
      return null;
    }
  }

  private openText(): TextStream | null {
    try {
      return ensureTextStream({ provider: "listenai" });
    } catch (error) {
      log.warn("text stream unavailable", safeErrorFields(error));
      return null;
    }
  }
}
