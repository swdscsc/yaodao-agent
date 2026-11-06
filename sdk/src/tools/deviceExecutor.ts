import { AgentCancelledError } from "../runtime/cancellation";
import { AgentError } from "../runtime/errors";
import { encodeUTF8 } from "../http/utf8";
import type {
  ToolCall,
  ToolExecutionContext,
  ToolExecutor,
  ToolExecutionOwner,
  ToolResult,
} from "./types";

export const MAX_DEVICE_TOOL_CALL_FRAME_BYTES = 64 << 10;

export interface DeviceToolBinding {
  protocol: "xiaoling" | "xiaozhi";
  originalName: string;
  timeoutMs?: number;
}

export interface DeviceToolResolution {
  sessionId: string;
  turnId: string;
  callId: string;
  result: Omit<ToolResult, "callId">;
}

export interface DeviceToolRouterOptions {
  emit?: (sessionId: string, frame: unknown) => void;
  startTimer?: (delayMs: number, callback: () => void) => unknown;
  cancelTimer?: (timerId: unknown) => void;
}

interface PendingDeviceCall {
  callId: string;
  resolve: (result: ToolResult) => void;
  reject: (error: AgentError) => void;
  unsubscribe: () => void;
  timerId: unknown;
}

export class DeviceToolRouter {
  private readonly pending = new Map<string, PendingDeviceCall>();
  private readonly emitFrame: (sessionId: string, frame: unknown) => void;
  private readonly startTimer: (delayMs: number, callback: () => void) => unknown;
  private readonly cancelTimer: (timerId: unknown) => void;

  constructor(options: DeviceToolRouterOptions = {}) {
    this.emitFrame = options.emit ?? ((sessionId, frame) => {
      host.emit(sessionId, { tag: "raw", val: JSON.stringify(frame) });
    });
    this.startTimer = options.startTimer ?? defaultStartTimer;
    this.cancelTimer = options.cancelTimer ?? defaultCancelTimer;
  }

  get pendingCount(): number {
    return this.pending.size;
  }

  executor(binding: DeviceToolBinding): ToolExecutor {
    validateBinding(binding);
    return {
      execute: (call, context) => this.execute(binding, call, context),
      cancel: (callId, reason, owner) => this.cancelCall(callId, reason, owner),
    };
  }

  resolve(resolution: DeviceToolResolution): boolean {
    const key = pendingKey(resolution.sessionId, resolution.turnId, resolution.callId);
    const pending = this.pending.get(key);
    if (!pending) return false;
    this.pending.delete(key);
    this.cancelTimer(pending.timerId);
    pending.unsubscribe();
    pending.resolve({ callId: resolution.callId, ...resolution.result });
    return true;
  }

  cancelSession(sessionId: string, reason = "Session disconnected"): void {
    for (const [key, pending] of Array.from(this.pending.entries())) {
      if (!key.startsWith(`${sessionId}\u0000`)) continue;
      this.finishWithError(key, pending, new AgentCancelledError(reason));
    }
  }

  private execute(
    binding: DeviceToolBinding,
    call: ToolCall,
    context: ToolExecutionContext,
  ): Promise<ToolResult> {
    context.cancellation.throwIfCancelled();
    const frame = buildDeviceToolFrame(binding, call, context.turnId);
    if (encodeUTF8(JSON.stringify(frame)).length > MAX_DEVICE_TOOL_CALL_FRAME_BYTES) {
      return Promise.reject(new AgentError(
        "AGENT_DEVICE_TOOL_FRAME_TOO_LARGE",
        "Device tool call frame exceeds the protocol limit",
        { phase: "tool" },
      ));
    }
    const key = pendingKey(context.sessionId, context.turnId, call.id);
    if (this.pending.has(key)) {
      return Promise.reject(new AgentError("AGENT_DEVICE_TOOL_DUPLICATE", "Device tool call is already pending", {
        phase: "tool",
      }));
    }
    const timeoutMs = boundedTimeout(binding.timeoutMs);
    let pending!: PendingDeviceCall;
    const promise = new Promise<ToolResult>((resolve, reject) => {
      const timerId = this.startTimer(timeoutMs, () => {
        this.finishWithError(key, pending, new AgentError(
          "AGENT_DEVICE_TOOL_TIMEOUT",
          "Device tool result timed out",
          { retryable: true, phase: "tool" },
        ));
      });
      const unsubscribe = context.cancellation.onCancel((reason) => {
        this.finishWithError(key, pending, new AgentCancelledError(reason));
      });
      pending = { callId: call.id, resolve, reject, unsubscribe, timerId };
      this.pending.set(key, pending);
    });

    try {
      this.emitFrame(context.sessionId, frame);
    } catch (error) {
      this.finishWithError(key, pending, new AgentError(
        "AGENT_DEVICE_TOOL_EMIT_FAILED",
        "Unable to dispatch device tool",
        { phase: "tool" },
      ));
    }
    return promise;
  }

  private cancelCall(callId: string, reason?: string, owner?: ToolExecutionOwner): void {
    if (owner) {
      const key = pendingKey(owner.sessionId, owner.turnId, callId);
      const pending = this.pending.get(key);
      if (pending) this.finishWithError(key, pending, new AgentCancelledError(reason));
      return;
    }
    const matches = Array.from(this.pending.entries()).filter(([, pending]) => pending.callId === callId);
    if (matches.length !== 1) return;
    const [key, pending] = matches[0];
    this.finishWithError(key, pending, new AgentCancelledError(reason));
  }

  private finishWithError(key: string, pending: PendingDeviceCall, error: AgentError): void {
    if (this.pending.get(key) !== pending) return;
    this.pending.delete(key);
    this.cancelTimer(pending.timerId);
    pending.unsubscribe();
    pending.reject(error);
  }
}

function buildDeviceToolFrame(binding: DeviceToolBinding, call: ToolCall, turnId: string): unknown {
  if (binding.protocol === "xiaoling") {
    return {
      type: "CUSTOM",
      nlp_origin: "xiaoling_mcp",
      payload: {
        method: "tools/call",
        id: call.id,
        turn_id: turnId,
        params: { name: binding.originalName, arguments: call.parsedArguments },
      },
    };
  }
  return {
    type: "CUSTOM",
    nlp_origin: "xiaozhi_mcp",
    payload: {
      jsonrpc: "2.0",
      method: "tools/call",
      id: call.id,
      turn_id: turnId,
      params: { name: binding.originalName, arguments: call.parsedArguments },
    },
  };
}

function validateBinding(binding: DeviceToolBinding): void {
  if (!binding.originalName || binding.originalName.length > 256) {
    throw new AgentError("AGENT_TOOL_BINDING_INVALID", "Invalid device tool name", {
      phase: "tool",
    });
  }
}

function pendingKey(sessionId: string, turnId: string, callId: string): string {
  return `${sessionId}\u0000${turnId}\u0000${callId}`;
}

function boundedTimeout(value?: number): number {
  if (!Number.isFinite(value) || Number(value) <= 0) return 30_000;
  return Math.min(Math.floor(Number(value)), 120_000);
}

function defaultStartTimer(delayMs: number, callback: () => void): unknown {
  const timerHost = typeof host === "undefined" ? undefined : host as typeof host & {
    timerStart?: (delayMs: number, callback: () => void) => string;
  };
  if (timerHost?.timerStart) return timerHost.timerStart(delayMs, callback);
  return setTimeout(callback, delayMs);
}

function defaultCancelTimer(timerId: unknown): void {
  const timerHost = typeof host === "undefined"
    ? undefined
    : host as typeof host & { timerCancel?: (timerId: string) => void };
  if (typeof timerId === "string" && timerHost?.timerCancel) {
    timerHost.timerCancel(timerId);
    return;
  }
  clearTimeout(timerId as ReturnType<typeof setTimeout>);
}
