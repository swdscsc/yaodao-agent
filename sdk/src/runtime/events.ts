import type { ModelRequest, ModelUsage } from "../model/types";
import type { ToolArtifact, ToolCall, ToolResult } from "../tools/types";
import type { AgentError } from "./errors";

export interface OutputMeta {
  emotion?: string;
  language?: string;
}

export type AgentEvent =
  | {
      type: "model.started";
      modelCallId: string;
      model: string;
      requestId: string;
      request: ModelRequest;
    }
  | { type: "output.delta"; text: string; meta?: OutputMeta }
  | { type: "tool.started"; call: ToolCall }
  | { type: "tool.completed"; call: ToolCall; result: ToolResult }
  | { type: "tool.failed"; call: ToolCall; error: AgentError }
  | { type: "usage"; modelCallId: string; usage: ModelUsage }
  | { type: "model.completed"; modelCallId: string; finishReason: string }
  | { type: "run.completed"; result: RunResult }
  | { type: "run.failed"; error: AgentError };

export interface AgentEventHandlers {
  onEvent?: (event: AgentEvent) => void;
}

export interface RunResult {
  status: "COMPLETED" | "AGENT_STOP";
  finalAnswer: string;
  stopReason: "completed" | "agent_stop";
  messages: import("../model/types").ChatMessage[];
  modelSteps: number;
  toolCalls: number;
  artifacts: ToolArtifact[];
  usage?: ModelUsage;
  toolResults?: Array<Pick<ToolResult, "callId" | "content" | "isError" | "control"> & {
    artifacts?: ToolArtifact[];
  }>;
}
