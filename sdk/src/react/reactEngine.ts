import type {
	ChatMessage,
	ChatModel,
	ModelRequest,
	ModelRunResult,
	ModelRunContext,
	ModelUsage,
	ToolChoice,
} from "../model/types";
import { encodeUTF8 } from "../http/utf8";
import {
	AgentCancelledError,
	CancellationTokenSource,
	type CancellationToken,
} from "../runtime/cancellation";
import type { AgentEvent, AgentEventHandlers, RunResult } from "../runtime/events";
import { AgentError, asAgentError } from "../runtime/errors";
import { DuplicateToolCallGuard } from "../tools/duplicateGuard";
import type { ToolRegistry } from "../tools/registry";
import { modelToolResultText, type ToolArtifact, type ToolCall, type ToolResult } from "../tools/types";

export interface ReActInput {
  turnId: string;
  modelName: string;
  messages: ChatMessage[];
  /** Number of contiguous history messages immediately before the current user message. */
  historyMessageCount?: number;
  model: ChatModel;
  tools: ToolRegistry;
  maxSteps: number;
  maxToolCalls: number;
  userText?: string;
  toolChoice?: ToolChoice;
  temperature?: number;
	maxTokens?: number;
	firstFrameTimeoutMs?: number;
	idleTimeoutMs?: number;
	totalTimeoutMs?: number;
	/** @deprecated Use totalTimeoutMs. */
	timeoutMs?: number;
  cancellation: CancellationToken;
	requestContext: Omit<ModelRunContext, "turnId">;
	fallback?: ModelFallbackPolicy;
}

export interface ModelFallbackCandidate {
	model: ChatModel;
	modelName: string;
}

export interface ModelFallbackPolicy {
	maxPrimaryAttempts: number;
	fallback?: ModelFallbackCandidate;
}

export interface ReActEngine {
  run(input: ReActInput, handlers: AgentEventHandlers): Promise<RunResult>;
  cancel(turnId: string, reason?: string): void;
}

interface ActiveRun {
  cancelled: boolean;
  reason?: string;
	terminalEmitted?: boolean;
	cancelRun?: (reason?: string) => void;
  cancelCurrent?: (reason?: string) => void;
}

export class DefaultReActEngine implements ReActEngine {
  private readonly active = new Map<string, ActiveRun>();

  async run(input: ReActInput, handlers: AgentEventHandlers): Promise<RunResult> {
    if (this.active.has(input.turnId)) {
      throw new AgentError("AGENT_TURN_ALREADY_RUNNING", "Turn is already running", {
        phase: "model",
      });
    }
    validateLimits(input.maxSteps, input.maxToolCalls);
		const cancellation = new CancellationTokenSource();
		const unsubscribeCancellation = input.cancellation.onCancel((reason) => cancellation.cancel(reason));
		const runInput: ReActInput = {
			...input,
			cancellation: cancellation.token,
			requestContext: {
				...input.requestContext,
				cancellation: cancellation.token,
			},
		};
		const active: ActiveRun = {
			cancelled: false,
			cancelRun: (reason) => cancellation.cancel(reason),
		};
    this.active.set(input.turnId, active);
    try {
			return await this.runSteps(runInput, handlers, active);
    } catch (error) {
      const normalized = asAgentError(error);
      if (!active.terminalEmitted) {
		active.terminalEmitted = true;
        try {
          emitEvent(handlers, { type: "run.failed", error: normalized });
        } catch {
          // Preserve the original terminal error when the failure observer is broken.
        }
      }
      throw normalized;
    } finally {
			unsubscribeCancellation();
      this.active.delete(input.turnId);
    }
  }

  cancel(turnId: string, reason?: string): void {
    const active = this.active.get(turnId);
    if (!active || active.cancelled) return;
    active.cancelled = true;
    active.reason = reason;
		active.cancelRun?.(reason);
    active.cancelCurrent?.(reason);
  }

  private async runSteps(
    input: ReActInput,
    handlers: AgentEventHandlers,
    active: ActiveRun,
  ): Promise<RunResult> {
    const messages = cloneMessages(input.messages);
		const historyEnd = messages.length - 1;
		const historyMessageCount = input.historyMessageCount ?? 0;
		const historyStart = historyEnd - historyMessageCount;
		validateHistoryBoundary(historyMessageCount, historyStart, historyEnd);
    const duplicateGuard = new DuplicateToolCallGuard();
		let modelSteps = 0;
		let modelAttempts = 0;
		let currentModelAttemptVisible = false;
		let toolCallCount = 0;
		let finalAnswer = "";
		let externallyVisible = false;
		let usage: ModelUsage | undefined;
		let historyReductionStage = 0;
		const artifacts: ToolArtifact[] = [];
		const toolResults: NonNullable<RunResult["toolResults"]> = [];

    while (true) {
      throwIfCancelled(input.cancellation, active);
      if (modelSteps >= input.maxSteps) {
        throw new AgentError("AGENT_REACT_STEP_LIMIT", "ReAct model step limit reached", {
          phase: "model",
        });
			}
			modelSteps += 1;
			const runCandidate = async (candidate: ModelFallbackCandidate): Promise<ModelRunResult> => {
				currentModelAttemptVisible = false;
				modelAttempts += 1;
				const modelCallId = boundedCorrelation(`${input.turnId}:model:${modelSteps}:attempt:${modelAttempts}`);
				const requestId = boundedCorrelation(`${input.requestContext.requestId}:model:${modelSteps}:attempt:${modelAttempts}`);
				const definitions = toolCallCount < input.maxToolCalls ? input.tools.definitions() : [];
				const request: ModelRequest = {
					modelCallId,
					purpose: "chat",
					model: candidate.modelName,
					messages: modelContextMessages(messages, historyStart, historyEnd, historyReductionStage),
					tools: definitions,
					toolChoice: definitions.length > 0 ? input.toolChoice ?? "auto" : "none",
					temperature: input.temperature,
					maxTokens: input.maxTokens,
					firstFrameTimeoutMs: input.firstFrameTimeoutMs,
					idleTimeoutMs: input.idleTimeoutMs,
					totalTimeoutMs: input.totalTimeoutMs ?? input.timeoutMs,
				};
				emitEvent(handlers, {
					type: "model.started",
					modelCallId,
					model: candidate.modelName,
					requestId,
					request,
				});
				let observerError: AgentError | undefined;
				let handle: ReturnType<ChatModel["run"]> | undefined;
				const observe = (event: AgentEvent): void => {
					if (observerError) return;
					try {
						emitEvent(handlers, event);
					} catch (error) {
						observerError = asAgentError(error, "AGENT_EVENT_HANDLER_FAILED", "response");
						handle?.cancel("Agent event observer failed");
					}
				};
				try {
					handle = candidate.model.run(request, {
						onTextDelta: (text) => {
							currentModelAttemptVisible = true;
						externallyVisible = true;
						finalAnswer += text;
						observe({ type: "output.delta", text });
					},
					onUsage: (value) => {
						usage = aggregateModelUsage(usage, value);
						observe({ type: "usage", modelCallId, usage: value });
					},
				}, {
					...input.requestContext,
					turnId: input.turnId,
					requestId,
					cancellation: input.cancellation,
				});
				} catch (error) {
					if (observerError) throw observerError;
					throw error;
				}
				if (observerError) {
					handle.cancel("Agent event observer failed");
					await handle.completed.catch(() => undefined);
					throw observerError;
				}
				active.cancelCurrent = (reason) => handle.cancel(reason);
				try {
					const result = await handle.completed;
					if (observerError) throw observerError;
					emitEvent(handlers, {
						type: "model.completed",
						modelCallId,
						finishReason: result.finishReason,
					});
					return result;
				} finally {
					active.cancelCurrent = undefined;
				}
			};
			const primary: ModelFallbackCandidate = { model: input.model, modelName: input.modelName };
			const primaryAttempts = input.fallback?.maxPrimaryAttempts ?? 1;
			if (!Number.isInteger(primaryAttempts) || primaryAttempts < 1 || primaryAttempts > 4) {
				throw new AgentError("AGENT_REACT_CONFIG_INVALID", "Invalid primary model attempt limit", {
					phase: "config",
				});
			}
			let modelResult: ModelRunResult | undefined;
			while (!modelResult) {
				let lastError: AgentError | undefined;
				for (let attempt = 0; attempt < primaryAttempts; attempt += 1) {
					try {
						modelResult = await runCandidate(primary);
						break;
					} catch (error) {
						lastError = asAgentError(error);
						if (isModelContextLengthError(lastError) && !currentModelAttemptVisible) break;
						if (externallyVisible || !retryableBeforeOutput(lastError)) throw lastError;
					}
				}
				const fallback = input.fallback?.fallback;
				const canUseFallback = !modelResult
					&& fallback
					&& !externallyVisible
					&& lastError
					&& retryableBeforeOutput(lastError);
				if (canUseFallback) {
					try {
						modelResult = await runCandidate(fallback);
					} catch (error) {
						lastError = asAgentError(error);
						if (!isModelContextLengthError(lastError) || currentModelAttemptVisible) throw lastError;
					}
				}
				if (modelResult) break;
				if (lastError && isModelContextLengthError(lastError) && !currentModelAttemptVisible) {
					if (historyReductionStage < HISTORY_REDUCTION_RATIOS.length) {
						historyReductionStage += 1;
						continue;
					}
					throw new AgentError("AGENT_MODEL_CONTEXT_TOO_LARGE", "Model context remains too large", {
						phase: "model",
					});
				}
				throw lastError ?? new AgentError(
					"AGENT_UPSTREAM_ERROR",
					"Model request failed",
					{ retryable: true, phase: "model" },
				);
			}
			throwIfCancelled(input.cancellation, active);
			if (isSafetyFinishReason(modelResult.finishReason)) {
				throw new AgentError("AGENT_MODEL_SAFETY_STOP", "Model response was blocked by safety policy", {
					phase: "model",
				});
			}

      if (modelResult.toolCalls.length === 0) {
        messages.push({ role: "assistant", content: modelResult.text });
        return complete(handlers, active, {
          status: "COMPLETED",
          finalAnswer,
          stopReason: "completed",
          messages,
          modelSteps,
          toolCalls: toolCallCount,
          artifacts,
          ...(usage ? { usage } : {}),
          toolResults,
        });
      }

      if (toolCallCount + modelResult.toolCalls.length > input.maxToolCalls) {
        throw new AgentError("AGENT_REACT_TOOL_LIMIT", "ReAct tool call limit reached", {
          phase: "tool",
        });
      }
      messages.push({
        role: "assistant",
        content: modelResult.text || null,
        toolCalls: modelResult.toolCalls,
      });
      for (const assistantCall of modelResult.toolCalls) {
        throwIfCancelled(input.cancellation, active);
        toolCallCount += 1;
        const toolRequestId = boundedCorrelation(`${input.requestContext.requestId}:tool:${toolCallCount}`);
        let call: ToolCall = {
          id: assistantCall.id,
          name: assistantCall.function.name,
          arguments: assistantCall.function.arguments,
					parsedArguments: {},
				};
        let result: ToolResult | undefined;
				let toolStarted = false;
        let executionError: unknown;
        try {
          result = await input.tools.execute({
            id: call.id,
            name: call.name,
            arguments: call.arguments,
          }, {
            sessionId: input.requestContext.sessionId,
            turnId: input.turnId,
            requestId: toolRequestId,
            appId: input.requestContext.appId,
            userText: input.userText,
            cancellation: input.cancellation,
          }, (validatedCall) => {
						call = validatedCall;
						externallyVisible = true;
						toolStarted = true;
						emitEvent(handlers, { type: "tool.started", call });
						duplicateGuard.add(call.name, call.parsedArguments);
					});
        } catch (error) {
          executionError = error;
        }
        if (executionError !== undefined) {
          const toolError = asAgentError(executionError, "AGENT_TOOL_EXECUTION_FAILED", "tool");
					if (toolError.code === "AGENT_EVENT_HANDLER_FAILED") throw toolError;
					if (!toolStarted) {
						externallyVisible = true;
						toolStarted = true;
						emitEvent(handlers, { type: "tool.started", call });
					}
          emitEvent(handlers, { type: "tool.failed", call, error: toolError });
          if (isTerminalToolError(toolError)) throw toolError;
          result = {
            callId: call.id,
            content: [{ type: "text", text: toolError.message }],
            isError: true,
            control: { agentStop: false },
            artifacts: [],
          };
        } else {
          if (!result) {
            throw new AgentError("AGENT_TOOL_PROTOCOL_ERROR", "Tool returned no result", {
              phase: "tool",
            });
          }
          emitEvent(handlers, { type: "tool.completed", call, result });
        }
        if (!result) {
          throw new AgentError("AGENT_TOOL_PROTOCOL_ERROR", "Tool returned no result", {
            phase: "tool",
          });
        }
				artifacts.push(...result.artifacts);
        toolResults.push(cloneToolResultForHistory(result));
        messages.push({
          role: "tool",
          content: modelToolResultText(result),
          toolCallId: call.id,
          name: call.name,
        });
        if (result.control.agentStop) {
          return complete(handlers, active, {
            status: "AGENT_STOP",
            finalAnswer,
            stopReason: "agent_stop",
            messages,
            modelSteps,
            toolCalls: toolCallCount,
            artifacts,
            ...(usage ? { usage } : {}),
            toolResults,
          });
        }
      }
    }
  }
}

function aggregateModelUsage(previous: ModelUsage | undefined, current: ModelUsage): ModelUsage {
	const cachedPromptTokens = (previous?.cachedPromptTokens ?? 0) + (current.cachedPromptTokens ?? 0);
	return {
		promptTokens: (previous?.promptTokens ?? 0) + current.promptTokens,
		completionTokens: (previous?.completionTokens ?? 0) + current.completionTokens,
		totalTokens: (previous?.totalTokens ?? 0) + current.totalTokens,
		...(cachedPromptTokens > 0 ? { cachedPromptTokens } : {}),
	};
}

function complete(handlers: AgentEventHandlers, active: ActiveRun, result: RunResult): RunResult {
  active.terminalEmitted = true;
  emitEvent(handlers, { type: "run.completed", result });
  return result;
}

function emitEvent(handlers: AgentEventHandlers, event: AgentEvent): void {
  try {
    handlers.onEvent?.(event);
  } catch {
    throw new AgentError("AGENT_EVENT_HANDLER_FAILED", "Agent event observer failed", {
      phase: "response",
    });
  }
}

function validateLimits(maxSteps: number, maxToolCalls: number): void {
  if (!Number.isInteger(maxSteps) || maxSteps < 1 || maxSteps > 20) {
    throw new AgentError("AGENT_REACT_CONFIG_INVALID", "Invalid ReAct step limit", { phase: "config" });
  }
  if (!Number.isInteger(maxToolCalls) || maxToolCalls < 0 || maxToolCalls > 64) {
    throw new AgentError("AGENT_REACT_CONFIG_INVALID", "Invalid ReAct tool limit", { phase: "config" });
  }
}

function throwIfCancelled(token: CancellationToken, active: ActiveRun): void {
  token.throwIfCancelled();
  if (active.cancelled) throw new AgentCancelledError(active.reason);
}

function cloneMessages(messages: ChatMessage[]): ChatMessage[] {
  return JSON.parse(JSON.stringify(messages)) as ChatMessage[];
}

const HISTORY_REDUCTION_RATIOS = [0.2, 0.5, 0.8] as const;

function modelContextMessages(
  messages: ChatMessage[],
  historyStart: number,
  historyEnd: number,
  reductionStage = 0,
): ChatMessage[] {
  if (historyStart === historyEnd || reductionStage === 0) return cloneMessages(messages);
  const groups = groupHistoryTurns(messages.slice(historyStart, historyEnd));
  const ratio = HISTORY_REDUCTION_RATIOS[Math.min(reductionStage, HISTORY_REDUCTION_RATIOS.length) - 1];
  const totalBytes = groups.reduce((sum, group) => sum + serializedBytes(group), 0);
  const targetBytes = Math.ceil(totalBytes * ratio);
  let removedBytes = 0;
  let removedGroups = 0;
  while (removedGroups < groups.length && removedBytes < targetBytes) {
    removedBytes += serializedBytes(groups[removedGroups]);
    removedGroups += 1;
  }
  return cloneMessages([
    ...messages.slice(0, historyStart),
    ...groups.slice(removedGroups).flat(),
    ...messages.slice(historyEnd),
  ]);
}

function validateHistoryBoundary(historyMessageCount: number, historyStart: number, historyEnd: number): void {
  if (!Number.isInteger(historyMessageCount) || historyMessageCount < 0 || historyStart < 0 || historyEnd < 0) {
    throw new AgentError("AGENT_REACT_CONFIG_INVALID", "Invalid history message boundary", { phase: "config" });
  }
}

function groupHistoryTurns(messages: ChatMessage[]): ChatMessage[][] {
  const groups: ChatMessage[][] = [];
  for (const message of messages) {
    if (message.role === "user" || groups.length === 0) groups.push([]);
    groups[groups.length - 1].push(message);
  }
  return groups;
}

function serializedBytes(messages: ChatMessage[]): number {
  return encodeUTF8(JSON.stringify(messages)).length;
}

function isModelContextLengthError(error: AgentError): boolean {
  return error.code === "AGENT_MODEL_CONTEXT_LENGTH_EXCEEDED";
}

function cloneToolResultForHistory(
  result: ToolResult,
): NonNullable<RunResult["toolResults"]>[number] {
  return JSON.parse(JSON.stringify({
    callId: result.callId,
    content: result.content,
    isError: result.isError,
    control: result.control,
    artifacts: result.artifacts,
  })) as NonNullable<RunResult["toolResults"]>[number];
}

function boundedCorrelation(value: string): string {
  return value.length <= 128 ? value : value.slice(value.length - 128);
}

function isTerminalToolError(error: AgentError): boolean {
  return error.code === "AGENT_CAPABILITY_QUOTA_EXCEEDED"
    || error.code === "AGENT_UNAUTHENTICATED"
    || error.code === "AGENT_IDENTITY_MISMATCH";
}

function retryableBeforeOutput(error: AgentError): boolean {
  if (error.code === "AGENT_CHAT_QUOTA_EXCEEDED"
    || error.code === "AGENT_CAPABILITY_QUOTA_EXCEEDED"
    || error.code === "AGENT_UNAUTHENTICATED"
    || error.code === "AGENT_IDENTITY_MISMATCH"
    || error.code === "AGENT_MODEL_CONFIG_INVALID") {
    return false;
  }
  return error.retryable
    || error.code === "AGENT_MODEL_CIRCUIT_OPEN"
    || error.code === "AGENT_UPSTREAM_TIMEOUT"
    || error.code === "AGENT_UPSTREAM_ERROR"
    || error.code === "AGENT_MODEL_PROTOCOL_ERROR";
}

function isSafetyFinishReason(reason: string): boolean {
  return reason === "content_filter" || reason === "stop_sensitive";
}
