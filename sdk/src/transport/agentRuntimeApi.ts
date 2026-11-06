import type { FunctionTool, ChatMessage, ToolChoice } from "../model/types";
import type { CancellationToken } from "../runtime/cancellation";
import { AgentError } from "../runtime/errors";
import type { AgentRuntimeRequestContext, AgentRuntimeTransportOptions } from "./agentRuntime";
import { AgentRuntimeTransport } from "./agentRuntime";

export interface TrustedIdentity {
  product_id: string;
  device_id: string;
  end_user_id: string;
  app_id?: string;
}

export interface AgentWarning {
  section: string;
  code: string;
  message: string;
}

export interface KnowledgeSource {
  index_id: string;
  source_type?: "request" | "device" | "product" | "role" | "hotfix" | "qa";
  doc_ids?: string[];
  limit?: number;
  threshold?: number;
}

export interface PrepareTurnRequest {
  turn_id: string;
  user_text: string;
  voice_profile_id?: string;
  app_id?: string;
  location_context?: {
    city?: string;
    location?: string;
    client_ip?: string;
  };
  include: PrepareTurnInclude[];
}

export type PrepareTurnInclude =
  | "configs"
  | "role"
  | "voice_profile"
  | "location"
  | "wakeup_word"
  | "knowledge_sources"
  | "memory_summary"
  | "openclaw_capabilities"
  | "tool_catalog_etag";

export interface AgentRuntimeMemoryPolicy {
  recall_enabled: boolean;
  store_enabled: boolean;
  preferences_enabled: boolean;
  subject_strategy: "voice_profile_then_vpr_group";
}

export interface AgentRuntimeDsaPolicy {
  enabled: boolean;
  system_prompt?: string;
  allowed_tool_ids: string[];
}

export interface AgentRuntimePolicy {
  memory: AgentRuntimeMemoryPolicy;
  dsa: AgentRuntimeDsaPolicy;
}

export interface AgentConfigLayer {
  revision: string;
  nlu_property: Record<string, unknown>;
  source: "product" | "device";
  default_agent_system_prompt?: string;
  tool_protocol_version?: string;
  runtime_policy?: AgentRuntimePolicy;
}

export interface RoleContext {
  default_role_id?: string;
  persona?: string;
  portrait?: string;
  knowledge_sources?: KnowledgeSource[];
}

export interface VoiceProfileContext {
  feature_id?: string;
  name?: string;
  hobbies?: Array<Record<string, unknown>>;
}

export interface PrepareTurnResponse {
  turn_id: string;
  context_version: string;
  identity: TrustedIdentity;
  product_config?: AgentConfigLayer;
  device_config?: AgentConfigLayer;
  role?: RoleContext;
  voice_profile?: VoiceProfileContext;
  location?: { city?: string };
  wakeup_word?: string;
  knowledge_sources?: KnowledgeSource[];
  memory_summary?: Record<string, unknown>;
  openclaw_capabilities?: Record<string, boolean>;
  tool_catalog_etag?: string;
  warnings: AgentWarning[];
}

export interface CompleteTurnRequest {
  status: "completed" | "rejected_quota" | "cancelled" | "failed_empty" | "failed_partial" | "failed_protocol";
  stop_reason: "completed" | "agent_stop" | "end_session" | "ignore_session" | "sensitive" | "quota" | "cancelled" | "timeout" | "model_error" | "tool_error" | "empty_response" | "protocol_error";
  error?: {
    code: "AGENT_MODEL_CONTEXT_TOO_LARGE";
    message: "Model context remains too large";
  };
  final_answer?: string;
  history_policy: "store" | "skip" | "abnormal";
  timing?: Record<string, number>;
  started_at?: string;
  agent_js_version?: string;
  voice_profile_id?: string;
  model_usage?: {
    prompt_tokens: number;
    completion_tokens: number;
    total_tokens: number;
    prompt_tokens_details?: { cached_tokens?: number };
  };
  interaction_record?: InteractionRecord;
}

export interface InteractionRecord {
  request: {
    temperature?: number;
    messages: Array<Record<string, unknown>>;
  };
  response: {
    messages: Array<Record<string, unknown>>;
    meta_data?: Record<string, unknown>;
    model_steps?: number;
    tool_calls?: number;
  };
}

export interface CompleteTurnResponse {
  turn_id: string;
  status: string;
  recorded_at?: string;
}

export interface KnowledgeQueryRequest {
  query: string;
  /** Optional compatibility filter; new clients let Runtime load trusted sources. */
  sources?: KnowledgeSource[];
}

export interface KnowledgeQueryResponse {
  knowledge_text: string;
  faq_direct_reply: boolean;
  warnings: AgentWarning[];
}

export interface MemoryRecallRequest {
  query: string;
  voice_profile_id?: string;
  limit?: number;
}

export interface MemoryRecallResponse {
  memory_text: string;
  preferences: PreferenceRecord[];
  warnings: AgentWarning[];
  long_memory_markdown?: string;
  fragments?: Array<{ id: string; text: string; score?: number }>;
}

export interface MemoryStoreRequest {
  messages: ChatMessage[];
  metadata?: Record<string, unknown>;
}

export interface PreferenceRecord {
  id: string;
  subject: "user" | "assistant";
  text: string;
  type?: string;
}

export interface PreferenceUpdateRequest {
  operations: Array<{
    op: "upsert" | "delete";
    id?: string;
    subject?: "user" | "assistant";
    text?: string;
    type?: string;
  }>;
}

export interface VoiceProfileHobbyRequest {
  voice_profile_id: string;
  events: VoiceProfileHobbyEvent[];
}

export type VoiceProfileHobbyEvent =
  | { op: "upsert"; id?: string; text: string; type?: string }
  | { op: "delete"; id: string };

export interface AiuiResolveRequest {
  text: string;
  location?: { latitude?: number; longitude?: number; city?: string };
}

export type AiuiOutcomeReason =
  | "accepted"
  | "missing_service"
  | "service_not_authorized"
  | "rc_4"
  | "unsupported_rc";

export interface AiuiSlot {
  name?: string;
  value?: string;
}

export interface AiuiWebhookOutcome {
  status: "not_configured" | "applied" | "failed";
}

export interface AiuiResolveResponse {
  handled: boolean;
  accepted: boolean;
  outcome: "direct_return" | "fallback";
  outcome_reason: AiuiOutcomeReason;
  service?: string;
  intent?: string;
  slots: AiuiSlot[];
  answer_text?: string;
  data: unknown[];
  webhook: {
    pre_request: AiuiWebhookOutcome;
    post_response: AiuiWebhookOutcome;
  };
  playlist?: MusicPlaylistItem[];
}

export type AgentFeature =
  | "chat"
  | "vpr"
  | "voice_clone"
  | "voice_base"
  | "voice_char_limit"
  | "voice_premium"
  | "vision"
  | "search"
  | "drawing"
  | "drawing_hd"
  | "music"
  | "favor"
  | "memory"
  | "wakeup_word"
  | "knowledge_document";

export interface UpgradeActionResponse {
  feature: AgentFeature;
  code: string;
  html?: string;
  plain_text: string;
  action?: {
    type: "qrcode" | "link" | "none";
    url?: string;
  };
}

export interface MusicPlaylistItem {
  item_id: string;
  name: string;
  playable: 0 | 1;
  url?: string;
  source?: string;
  duration?: number;
  artists?: Array<{ id: string; name: string }>;
  album?: { id: string; name: string };
  cover_url?: string;
  file_name?: string;
  file_path?: string;
}

export type MusicPlayback = "kuwo" | "netease" | "general" | "audio_link" | "tf_card";

export type DeviceActionRequest =
  | { action: "show_upgrade"; feature: AgentFeature; code: string }
  | { action: "music_playlist"; playback: MusicPlayback; items: MusicPlaylistItem[] }
  | { action: "netease_token_refresh" }
  | { action: "playback_exit" };

export type ToolBinding =
  | { type: "platform"; tool_id: string; source?: string; timeout_ms?: number; quota_failure_policy?: "return_tool_error" | "stop_turn" }
  | { type: "device"; protocol: "xiaoling" | "xiaozhi"; original_name: string; source?: string; timeout_ms?: number };

export interface DeviceCapability {
  protocol: "xiaoling" | "xiaozhi";
  original_name: string;
  definition: FunctionTool;
  alias?: string;
}

export interface ToolCatalogResponse {
  tools: FunctionTool[];
  tool_bindings: Record<string, ResolvedToolBinding>;
  device_capabilities: DeviceCapability[];
  etag: string;
}

export interface ToolResolveClientTool {
  definition: FunctionTool;
  binding_id?: string;
  priority: "explicit" | "configured";
  source?: "external" | "xiaoling";
  enabled: boolean;
}

export interface ToolResolveRequest {
  client_tools: ToolResolveClientTool[];
}

export type ResolvedToolBinding =
  | ToolBinding
  | { type: "client"; binding_id: string };

export interface ToolResolveResponse {
  tools: FunctionTool[];
  tool_bindings: Record<string, ResolvedToolBinding>;
  device_capabilities: DeviceCapability[];
  enabled_mcp_server_ids: string[];
  tool_choice?: ToolChoice;
  etag: string;
}

export interface WriteResponse { status: "accepted"; }

export class AgentRuntimeClient {
  private readonly transport: AgentRuntimeTransport;

  constructor(options: AgentRuntimeTransportOptions) {
    this.transport = new AgentRuntimeTransport(options);
  }

  prepareTurn(body: PrepareTurnRequest, context: AgentRuntimeRequestContext, cancellation: CancellationToken): Promise<PrepareTurnResponse> {
    return this.post("/turns/prepare", body, context, cancellation);
  }

  completeTurn(turnId: string, body: CompleteTurnRequest, context: AgentRuntimeRequestContext, cancellation: CancellationToken): Promise<CompleteTurnResponse> {
    return this.post(`/turns/${pathSegment(turnId)}/complete`, body, context, cancellation);
  }

  queryKnowledge(body: KnowledgeQueryRequest, context: AgentRuntimeRequestContext, cancellation: CancellationToken): Promise<KnowledgeQueryResponse> {
    return this.post("/knowledge/query", body, context, cancellation);
  }

  recallMemory(body: MemoryRecallRequest, context: AgentRuntimeRequestContext, cancellation: CancellationToken): Promise<MemoryRecallResponse> {
    return this.post("/memory/recall", body, context, cancellation);
  }

  storeMemory(body: MemoryStoreRequest, context: AgentRuntimeRequestContext, cancellation: CancellationToken): Promise<WriteResponse> {
    return this.post("/memory/store", {
      ...body,
      messages: body.messages.map(toWireMemoryMessage),
    }, context, cancellation);
  }

  getPreferences(voiceProfileId: string | undefined, context: AgentRuntimeRequestContext, cancellation: CancellationToken): Promise<{ preferences: PreferenceRecord[] }> {
    const query = voiceProfileId ? `?voice_profile_id=${encodeURIComponent(voiceProfileId)}` : "";
    return this.get(`/preferences${query}`, context, cancellation);
  }

  updatePreferences(body: PreferenceUpdateRequest, context: AgentRuntimeRequestContext, cancellation: CancellationToken): Promise<WriteResponse> {
    return this.request("/preferences", "PUT", body, context, cancellation);
  }

  updateVoiceProfileHobbies(body: VoiceProfileHobbyRequest, context: AgentRuntimeRequestContext, cancellation: CancellationToken): Promise<WriteResponse> {
    return this.request("/voice-profile/hobbies", "PATCH", body, context, cancellation);
  }

  resolveAiui(body: AiuiResolveRequest, context: AgentRuntimeRequestContext, cancellation: CancellationToken): Promise<AiuiResolveResponse> {
    return this.post("/aiui/resolve", body, context, cancellation);
  }

  async getToolCatalog(etag: string | undefined, context: AgentRuntimeRequestContext, cancellation: CancellationToken): Promise<ToolCatalogResponse | null> {
    const query = etag ? `?if_none_match=${encodeURIComponent(etag)}` : "";
    const response = await this.transport.requestJSONResponse<ToolCatalogResponse>({
      path: `/tools/catalog${query}`,
      method: "GET",
      context,
    }, cancellation);
    if (response.status === 304) return null;
    if (response.body === undefined) {
      throw new AgentError("AGENT_RESPONSE_INVALID", "Agent Runtime returned an empty tool catalog", {
        phase: "transport",
      });
    }
    return response.body;
  }

  resolveTools(body: ToolResolveRequest, context: AgentRuntimeRequestContext, cancellation: CancellationToken): Promise<ToolResolveResponse> {
    return this.post("/tools/resolve", body, context, cancellation);
  }

  getUpgradeAction(feature: AgentFeature, code: string, context: AgentRuntimeRequestContext, cancellation: CancellationToken): Promise<UpgradeActionResponse> {
    const query = `?feature=${encodeURIComponent(feature)}&code=${encodeURIComponent(code)}`;
    return this.get(`/upgrade-action${query}`, context, cancellation);
  }

  dispatchDeviceAction(body: DeviceActionRequest, context: AgentRuntimeRequestContext, cancellation: CancellationToken): Promise<WriteResponse> {
    return this.post("/device/actions/dispatch", body, context, cancellation);
  }

  private get<T>(path: string, context: AgentRuntimeRequestContext, cancellation: CancellationToken): Promise<T> {
    return this.request(path, "GET", undefined, context, cancellation);
  }

  private post<T>(path: string, body: unknown, context: AgentRuntimeRequestContext, cancellation: CancellationToken): Promise<T> {
    return this.request(path, "POST", body, context, cancellation);
  }

  private request<T>(path: string, method: string, body: unknown, context: AgentRuntimeRequestContext, cancellation: CancellationToken): Promise<T> {
    return this.transport.requestJSON<T>({ path, method, body, context }, cancellation);
  }
}

function pathSegment(value: string): string {
  return encodeURIComponent(value);
}

/**
 * Convert the SDK history shape to the Agent Runtime wire shape.
 *
 * @created by huangzihao at 2026-07-17 11:20:00
 * @updated by huangzihao at 2026-07-17 11:20:00
 * @param message
 * @returns
 */
function toWireMemoryMessage(message: ChatMessage): Record<string, unknown> {
  const wire: Record<string, unknown> = {
    role: message.role,
    content: message.content,
  };
  if (message.name) wire.name = message.name;
  if (message.toolCallId) wire.tool_call_id = message.toolCallId;
  if (message.toolCalls) wire.tool_calls = message.toolCalls;
  return wire;
}
