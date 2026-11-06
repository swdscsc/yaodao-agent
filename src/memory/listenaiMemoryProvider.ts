import type { PreferenceRecord } from "@listenai/agent-sdk";
import { runtimeClient } from "../context/listenaiContextProvider";
import { requestContext, type VoiceTurnContext } from "../types";
import { isOptionalDependencyError } from "../errors/optionalDependency";
import { boundedCurrentUserText } from "../text/utf8Budget";

export interface MemoryRecallResult {
  longMemory: string;
  preferences: PreferenceRecord[];
  warnings: string[];
}

export interface MemoryProvider {
  recall(context: VoiceTurnContext): Promise<MemoryRecallResult>;
}

export class ListenAIMemoryProvider implements MemoryProvider {
  async recall(context: VoiceTurnContext): Promise<MemoryRecallResult> {
    const policy = context.memoryPolicy;
    if (!policy.recall_enabled && !policy.preferences_enabled) {
      return { longMemory: "", preferences: [], warnings: [] };
    }
    try {
      const response = await runtimeClient(context).recallMemory({
        query: boundedCurrentUserText(context.userText),
        ...(context.voiceProfileId ? { voice_profile_id: context.voiceProfileId } : {}),
      }, requestContext(context, "memory-recall"), context.cancellation);
      return {
        longMemory: response.memory_text,
        preferences: response.preferences,
        warnings: response.warnings.map((warning) => warning.code),
      };
    } catch (error) {
      if (!isOptionalDependencyError(error)) throw error;
      return { longMemory: "", preferences: [], warnings: ["memory.unavailable"] };
    }
  }
}
