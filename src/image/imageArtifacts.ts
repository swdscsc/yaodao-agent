export interface ImageArtifact extends Record<string, unknown> {
  type: "image";
  kind: "camera" | "generated" | "edited" | "input" | "unknown";
  url?: string;
  data?: string;
}

export const GENERATED_IMAGE_HISTORY_TEXT = "这是我的作品，希望你喜欢。";

export function mapImageArtifacts(artifacts: unknown[]): ImageArtifact[] {
  const output: ImageArtifact[] = [];
  for (const value of artifacts) {
    if (!isRecord(value)) continue;
    const artifact = value;
    if (artifact.type !== "image") continue;
    const url = imageURL(artifact);
    const data = !url && typeof artifact.data === "string" ? artifact.data : undefined;
    if (!url && !data) continue;
    output.push({
      type: "image",
      kind: imageKind(artifact.kind),
      ...(url ? { url } : {}),
      ...(data ? { data } : {}),
    });
  }
  return output;
}

export function mapToolImageArtifacts(
  toolName: string,
  result: {
    content: unknown[];
    artifacts: unknown[];
  },
): ImageArtifact[] {
  const inferredKind = toolImageKind(toolName);
  const candidates = [
    ...result.artifacts,
    ...result.content,
  ];
  const output: ImageArtifact[] = [];
  const seen = new Set<string>();
  for (const artifact of candidates) {
    if (!isRecord(artifact) || artifact.type !== "image") continue;
    const mapped = mapImageArtifacts([{
      type: "image",
      kind: artifact.kind ?? inferredKind,
      ...(typeof artifact.url === "string" ? { url: artifact.url } : {}),
      ...(typeof artifact.data === "string" ? { data: artifact.data } : {}),
    }])[0];
    if (!mapped) continue;
    const identity = `${mapped.kind}\u0000${imageArtifactSource(mapped)}`;
    if (seen.has(identity)) continue;
    seen.add(identity);
    output.push(mapped);
  }
  return output;
}

export function imageArtifactSource(artifact: ImageArtifact): string {
  return artifact.url || artifact.data || "";
}

const PERSISTED_IMAGE_QUERY_ALLOWLIST = new Set(["x-oss-process"]);

export function persistenceSafeImageSource(artifact: ImageArtifact): string {
  const raw = imageArtifactSource(artifact).trim();
  const normalized = normalizeClosedToolContent({
    type: "image",
    kind: "input",
    url: raw,
  });
  const source = normalized?.type === "image" ? normalized.url ?? "" : "";
  if (!source || source.length > 8_192 || /[\s\\]/.test(source)) return "";
  const parsed = /^(https:\/\/([^/?#]+))([^?#]*)(?:\?([^#]*))?(?:#.*)?$/i.exec(source);
  if (!parsed || !parsed[2] || parsed[2].includes("@")) return "";
  const safeQuery: string[] = [];
  for (const item of (parsed[4] ?? "").split("&")) {
    if (!item) continue;
    const separator = item.indexOf("=");
    const rawName = separator >= 0 ? item.slice(0, separator) : item;
    let name = "";
    try {
      name = decodeURIComponent(rawName.replace(/\+/g, "%20")).toLowerCase();
    } catch {
      continue;
    }
    if (PERSISTED_IMAGE_QUERY_ALLOWLIST.has(name)) safeQuery.push(item);
  }
  const output = `${parsed[1]}${parsed[3]}${safeQuery.length > 0 ? `?${safeQuery.join("&")}` : ""}`;
  return output.length <= 8_192 ? output : "";
}

function imageKind(value: unknown): ImageArtifact["kind"] {
  if (value === "camera" || value === "generated" || value === "edited" || value === "input") return value;
  return "unknown";
}

function toolImageKind(toolName: string): ImageArtifact["kind"] {
  const normalized = toolName.toLowerCase();
  if (normalized.includes("take_photo") || normalized.includes("camera")) return "camera";
  if (normalized.includes("edit_image")) return "edited";
  if (normalized.includes("draw_image") || normalized.includes("my_image")) return "generated";
  return "unknown";
}

function imageURL(artifact: Record<string, unknown>): string | undefined {
  if (typeof artifact.url === "string" && artifact.url) return artifact.url;
  if (typeof artifact.image === "string" && artifact.image) return artifact.image;
  if (isRecord(artifact.image_url) && typeof artifact.image_url.url === "string") {
    return artifact.image_url.url;
  }
  return undefined;
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}
import { normalizeClosedToolContent } from "@listenai/agent-sdk";
