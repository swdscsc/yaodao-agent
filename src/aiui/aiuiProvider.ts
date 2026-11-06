import type { AiuiResolveResponse, MusicPlaylistItem } from "@listenai/agent-sdk";
import { runtimeClient } from "../context/listenaiContextProvider";
import { requestContext, type VoiceTurnContext } from "../types";
import { interpretAiuiResponse } from "./aiuiDecision";
import { isOptionalDependencyError } from "../errors/optionalDependency";

export interface AiuiDecision {
  handled: boolean;
  outcomeReason?: string;
  answer?: string;
  response?: AiuiResolveResponse;
  warning?: string;
  frames: Array<Record<string, unknown>>;
  playlist: MusicPlaylistItem[];
}

export interface AiuiProvider {
  resolve(context: VoiceTurnContext, city?: string): Promise<AiuiDecision>;
}

export class ListenAIAiuiProvider implements AiuiProvider {
  async resolve(context: VoiceTurnContext, city?: string): Promise<AiuiDecision> {
    if (context.config.runtime.capabilities.aiui !== true) {
      return { handled: false, frames: [], playlist: [] };
    }
    try {
      const client = runtimeClient(context);
      const response = await client.resolveAiui({
        text: context.userText,
        ...(city ? { location: { city } } : {}),
      }, requestContext(context, "aiui"), context.cancellation);
      const interpreted = interpretAiuiResponse(response, context.userText, context.turnId);
      let warning: string | undefined;
      if (interpreted.handled && interpreted.playlist.length > 0) {
        try {
          await client.dispatchDeviceAction({
            action: "music_playlist",
            playback: "kuwo",
            items: interpreted.playlist,
          }, requestContext(context, "aiui-playlist"), context.cancellation);
        } catch (error) {
          if (!isOptionalDependencyError(error)) throw error;
          warning = "aiui.playlist_dispatch_failed";
        }
      }
      return {
        ...interpreted,
        response,
        ...(warning ? { warning } : {}),
      };
    } catch (error) {
      if (!isOptionalDependencyError(error)) throw error;
      return { handled: false, frames: [], playlist: [], warning: "aiui.unavailable" };
    }
  }
}
