import type { AgentError } from "@listenai/agent-sdk";

export type TurnCompletionStatus =
  | "completed"
  | "rejected_quota"
  | "cancelled"
  | "failed_empty"
  | "failed_partial"
  | "failed_protocol";

export type PublicStopReason =
  | "completed"
  | "agent_stop"
  | "end_session"
  | "ignore_session"
  | "sensitive"
  | "quota"
  | "cancelled"
  | "timeout"
  | "model_error"
  | "tool_error"
  | "empty_response"
  | "protocol_error";

export function mapAgentErrorStop(error: AgentError, hasOutput: boolean): {
  status: TurnCompletionStatus;
  reason: PublicStopReason;
  historyPolicy: "store" | "skip" | "abnormal";
} {
  if (error.code === "AGENT_CHAT_QUOTA_EXCEEDED" || error.code === "AGENT_CAPABILITY_QUOTA_EXCEEDED") {
    return { status: "rejected_quota", reason: "quota", historyPolicy: "abnormal" };
  }
  if (error.code === "AGENT_CANCELLED") {
    return { status: "cancelled", reason: "cancelled", historyPolicy: "skip" };
  }
  if (error.code === "AGENT_MODEL_SAFETY_STOP") {
    return {
      status: hasOutput ? "failed_partial" : "failed_empty",
      reason: "sensitive",
      historyPolicy: "skip",
    };
  }
  if (error.code === "AGENT_UPSTREAM_TIMEOUT") {
    return { status: hasOutput ? "failed_partial" : "failed_empty", reason: "timeout", historyPolicy: "skip" };
  }
  if (error.code === "AGENT_MODEL_EMPTY_RESPONSE") {
    return {
      status: hasOutput ? "failed_partial" : "failed_empty",
      reason: "empty_response",
      historyPolicy: "skip",
    };
  }
  if (error.code.includes("PROTOCOL") || error.code === "AGENT_RESPONSE_INVALID") {
    return { status: "failed_protocol", reason: "protocol_error", historyPolicy: "skip" };
  }
  return {
    status: hasOutput ? "failed_partial" : "failed_empty",
    reason: error.phase === "tool" ? "tool_error" : "model_error",
    historyPolicy: "skip",
  };
}
