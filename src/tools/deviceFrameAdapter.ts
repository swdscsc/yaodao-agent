import { imageArtifactSource, type ImageArtifact } from "../image/imageArtifacts";
import { utf8ByteLength } from "../text/utf8Budget";

export const MAX_DEVICE_TOOL_EVENT_FRAME_BYTES = 64 << 10;

export function buildExitFrame(): Record<string, unknown> {
  return buildToolCallFrame("ls.built_in.exit", {}, String(Date.now()), "xiaoling");
}

export function buildEndSessionFrame(): Record<string, unknown> {
  return buildToolCallFrame("ls.built_in.exit", {}, String(Date.now()), "xiaoling");
}

export function buildToolCallFrame(
  name: string,
  args: Record<string, unknown>,
  callId: string,
  protocol: "xiaoling" | "xiaozhi",
): Record<string, unknown> {
  return {
    type: "CUSTOM",
    nlp_origin: protocol === "xiaoling" ? "xiaoling_mcp" : "xiaozhi_mcp",
    payload: {
      ...(protocol === "xiaozhi" ? { jsonrpc: "2.0" } : {}),
      method: "tools/call",
      id: callId,
      params: { name, arguments: args },
    },
  };
}

export function buildImageArtifactFrame(
  artifact: ImageArtifact,
  callId: string,
  index: number,
): Record<string, unknown> | null {
  const frame = buildToolCallFrame(
    "ls.built_in.show_image",
    { url: imageArtifactSource(artifact) },
    `${callId}:image:${index + 1}`,
    "xiaoling",
  );
  return utf8ByteLength(JSON.stringify(frame)) <= MAX_DEVICE_TOOL_EVENT_FRAME_BYTES
    ? frame
    : null;
}
