import { AgentError } from "@listenai/agent-sdk";

const OPTIONAL_DEPENDENCY_CODES = new Set([
  "AGENT_UPSTREAM_ERROR",
  "AGENT_UPSTREAM_TIMEOUT",
  "upstream-error",
  "timeout-io",
]);

export function isOptionalDependencyError(error: unknown): boolean {
  return error instanceof AgentError && OPTIONAL_DEPENDENCY_CODES.has(error.code);
}
