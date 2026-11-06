import type { FunctionTool } from "../model/types";
import { encodeUTF8, utf8ByteLength } from "../http/utf8";
import { AgentError, asAgentError } from "../runtime/errors";
import type {
  RegisteredTool,
  ToolCall,
  ToolExecutionContext,
  ToolExecutor,
  ToolResult,
} from "./types";
import { normalizeClosedToolResult } from "./types";

export interface ToolRegistryOptions {
  protectedNames?: string[];
  maxTools?: number;
  maxTotalSchemaBytes?: number;
  maxArgumentBytes?: number;
  maxArgumentDepth?: number;
  maxSchemaBytes?: number;
  maxSchemaDepth?: number;
}

export function validateFunctionToolDefinition(
  definition: FunctionTool,
  options: Pick<ToolRegistryOptions, "maxSchemaBytes" | "maxSchemaDepth"> = {},
): void {
  normalizeDefinition(
    definition,
    options.maxSchemaBytes ?? 64 << 10,
    options.maxSchemaDepth ?? 16,
  );
}

export class ToolRegistry {
  private readonly tools = new Map<string, RegisteredTool>();
  private readonly protectedNames: Set<string>;
  private readonly maxTools: number;
  private readonly maxTotalSchemaBytes: number;
  private readonly maxArgumentBytes: number;
  private readonly maxArgumentDepth: number;
  private readonly maxSchemaBytes: number;
  private readonly maxSchemaDepth: number;
  private totalSchemaBytes = 0;

  constructor(options: ToolRegistryOptions = {}) {
    this.protectedNames = new Set(options.protectedNames ?? []);
    this.maxTools = boundedRegistryLimit(options.maxTools, 128);
    this.maxTotalSchemaBytes = boundedRegistryLimit(options.maxTotalSchemaBytes, 512 << 10);
    this.maxArgumentBytes = options.maxArgumentBytes ?? 64 << 10;
    this.maxArgumentDepth = options.maxArgumentDepth ?? 16;
    this.maxSchemaBytes = options.maxSchemaBytes ?? 64 << 10;
    this.maxSchemaDepth = options.maxSchemaDepth ?? 16;
  }

  register(definition: FunctionTool, executor: ToolExecutor): void {
    this.registerBatch([{ definition, executor }]);
  }

  registerBatch(registrations: readonly RegisteredTool[]): void {
    const staged: RegisteredTool[] = [];
    const names = new Set(this.tools.keys());
    let totalSchemaBytes = this.totalSchemaBytes;
    for (const registration of registrations) {
      const definition = normalizeDefinition(
        registration.definition,
        this.maxSchemaBytes,
        this.maxSchemaDepth,
      );
      const name = definition.function.name;
      if (this.protectedNames.has(name)) {
        throw new AgentError("AGENT_TOOL_PROTECTED", `Tool name is protected: ${name}`, {
          phase: "tool",
        });
      }
      if (names.has(name)) {
        throw new AgentError("AGENT_TOOL_DUPLICATE", `Tool already registered: ${name}`, {
          phase: "tool",
        });
      }
      const definitionBytes = utf8ByteLength(JSON.stringify(definition));
      if (names.size >= this.maxTools
        || totalSchemaBytes + definitionBytes > this.maxTotalSchemaBytes) {
        throw new AgentError("AGENT_TOOL_REGISTRY_LIMIT", "Tool registry hard limit exceeded", {
          phase: "tool",
        });
      }
      names.add(name);
      totalSchemaBytes += definitionBytes;
      staged.push({ definition, executor: registration.executor });
    }
    for (const registration of staged) {
      this.tools.set(registration.definition.function.name, registration);
    }
    this.totalSchemaBytes = totalSchemaBytes;
  }

  definitions(): FunctionTool[] {
    return Array.from(this.tools.values(), ({ definition }) => cloneJSON(definition));
  }

  has(name: string): boolean {
    return this.tools.has(name);
  }

  async execute(
    input: Omit<ToolCall, "parsedArguments">,
    context: ToolExecutionContext,
    onValidated?: (call: ToolCall) => void,
  ): Promise<ToolResult> {
    context.cancellation.throwIfCancelled();
    if (!/^[A-Za-z0-9._:-]{1,128}$/.test(input.id)) {
      throw toolProtocolError("Tool call ID is invalid");
    }
    const registered = this.tools.get(input.name);
    if (!registered) {
      throw new AgentError("AGENT_TOOL_NOT_FOUND", `Tool is not registered: ${input.name}`, {
        phase: "tool",
      });
    }
    const parsedArguments = parseArguments(input.arguments, this.maxArgumentBytes, this.maxArgumentDepth);
    validateSchema(registered.definition.function.parameters, parsedArguments);
    const call: ToolCall = { ...input, parsedArguments };
    onValidated?.(call);
    let unsubscribe: () => void = () => undefined;
    if (registered.executor.cancel) {
      unsubscribe = context.cancellation.onCancel((reason) => {
        registered.executor.cancel?.(input.id, reason, {
          sessionId: context.sessionId,
          turnId: context.turnId,
        });
      });
    }
    try {
      const result = await registered.executor.execute(call, context);
      return normalizeToolResult(result, input.id);
    } catch (error) {
      throw asAgentError(error, "AGENT_TOOL_EXECUTION_FAILED", "tool");
    } finally {
      unsubscribe();
    }
  }
}

function boundedRegistryLimit(value: number | undefined, hardMaximum: number): number {
  if (!Number.isSafeInteger(value) || Number(value) < 1) return hardMaximum;
  return Math.min(Number(value), hardMaximum);
}

const MAX_RESULT_CONTENT_ITEMS = 64;
const MAX_RESULT_TEXT_BYTES = 64 << 10;
const MAX_RESULT_STRUCTURED_ITEM_BYTES = 520 << 10;
const MAX_RESULT_ARTIFACTS = 16;
const MAX_RESULT_ARTIFACT_BYTES = 520 << 10;
const MAX_RESULT_ARTIFACT_TOTAL_BYTES = 1 << 20;

function normalizeToolResult(value: unknown, expectedCallId: string): ToolResult {
  const normalizedResult = normalizeClosedToolResult(value, expectedCallId, true);
  if (!normalizedResult) {
    throw toolProtocolError("Tool returned a malformed result");
  }
  if (normalizedResult.content.length > MAX_RESULT_CONTENT_ITEMS) {
    throw toolProtocolError("Tool returned too many content items");
  }
  const content: ToolResult["content"] = [];
  let textBytes = 0;
  for (const normalized of normalizedResult.content) {
    if (normalized.type === "text") {
      const separatorBytes = content.some((item) => item.type === "text" && item.text) ? 1 : 0;
      const remaining = Math.max(0, MAX_RESULT_TEXT_BYTES - textBytes - separatorBytes);
      const text = truncateUTF8(normalized.text, remaining);
      if (text) {
        content.push({ type: "text", text });
        textBytes += separatorBytes + encodeUTF8(text).length;
      }
      continue;
    }
    if (encodeUTF8(JSON.stringify(normalized)).length > MAX_RESULT_STRUCTURED_ITEM_BYTES) {
      throw toolProtocolError("Tool returned oversized structured content");
    }
    content.push(normalized);
  }
  if (normalizedResult.artifacts.length > MAX_RESULT_ARTIFACTS) {
    throw toolProtocolError("Tool returned too many artifacts");
  }
  const artifacts: ToolResult["artifacts"] = [];
  let artifactBytes = 0;
  for (const artifact of normalizedResult.artifacts) {
    artifactBytes += encodeUTF8(JSON.stringify(artifact)).length;
    if (encodeUTF8(JSON.stringify(artifact)).length > MAX_RESULT_ARTIFACT_BYTES) {
      throw toolProtocolError("Tool returned an oversized artifact");
    }
    if (artifactBytes > MAX_RESULT_ARTIFACT_TOTAL_BYTES) {
      throw toolProtocolError("Tool artifact payload is too large");
    }
    artifacts.push(artifact);
  }
  return {
    callId: expectedCallId,
    content,
    isError: normalizedResult.isError,
    control: { agentStop: normalizedResult.control.agentStop },
    artifacts,
  };
}

function truncateUTF8(value: string, maximumBytes: number): string {
  if (encodeUTF8(value).length <= maximumBytes) return value;
  let output = "";
  let bytes = 0;
  for (const character of value) {
    const size = encodeUTF8(character).length;
    if (bytes + size > maximumBytes) break;
    output += character;
    bytes += size;
  }
  return output;
}

function toolProtocolError(message: string): AgentError {
  return new AgentError("AGENT_TOOL_PROTOCOL_ERROR", message, { phase: "tool" });
}

function normalizeDefinition(
  definition: FunctionTool,
  maxSchemaBytes: number,
  maxSchemaDepth: number,
): FunctionTool {
  const name = definition?.function?.name;
  if (definition?.type !== "function" || !name || !/^[A-Za-z0-9_-]{1,64}$/.test(name)) {
    throw new AgentError("AGENT_TOOL_DEFINITION_INVALID", "Invalid function tool definition", {
      phase: "tool",
    });
  }
  if (!isRecord(definition.function.parameters)) {
    throw new AgentError("AGENT_TOOL_DEFINITION_INVALID", `Invalid schema for tool ${name}`, {
      phase: "tool",
    });
  }
  if (definition.function.parameters.type !== "object") {
    throw definitionError(`Tool ${name} parameters must have top-level type object`);
  }
  if (definition.function.description !== undefined
    && (typeof definition.function.description !== "string"
      || utf8ByteLength(definition.function.description) > MAX_SCHEMA_DESCRIPTION_BYTES)) {
    throw definitionError(`Tool ${name} description is invalid`);
  }
  if (valueDepthExceeds(definition.function.parameters, maxSchemaDepth)) {
    throw definitionError(`Tool ${name} schema is too deeply nested`);
  }
  validateSchemaDefinition(definition.function.parameters, maxSchemaDepth);
  let serialized: string;
  try {
    serialized = JSON.stringify(definition.function.parameters);
  } catch {
    throw definitionError(`Tool ${name} schema is not serializable`);
  }
  if (utf8ByteLength(serialized) > maxSchemaBytes) {
    throw definitionError(`Tool ${name} schema is too large`);
  }
  return {
    type: "function",
    function: {
      name,
      description: definition.function.description,
      parameters: JSON.parse(serialized) as Record<string, unknown>,
    },
  };
}

function definitionError(message: string): AgentError {
  return new AgentError("AGENT_TOOL_DEFINITION_INVALID", message, { phase: "tool" });
}

function parseArguments(raw: string, maxBytes: number, maxDepth: number): Record<string, unknown> {
  if (encodeUTF8(raw).length > maxBytes) throw argumentError("Tool arguments are too large");
  let parsed: unknown;
  try {
    parsed = JSON.parse(raw) as unknown;
  } catch {
    throw argumentError("Tool arguments are not valid JSON");
  }
  if (!isRecord(parsed)) throw argumentError("Tool arguments must be an object");
  if (valueDepthExceeds(parsed, maxDepth)) throw argumentError("Tool arguments are too deeply nested");
  return parsed;
}

function validateSchema(schema: Record<string, unknown>, value: Record<string, unknown>): void {
  validateSchemaValue(schema, value, "arguments");
}

const SCHEMA_TYPES = new Set(["object", "array", "string", "number", "integer", "boolean", "null"]);
const MAX_SCHEMA_PROPERTIES = 128;
const MAX_SCHEMA_TOTAL_PROPERTIES = 256;
const MAX_SCHEMA_REQUIRED = 128;
const MAX_SCHEMA_ENUM = 128;
const MAX_SCHEMA_NODES = 512;
const MAX_SCHEMA_DESCRIPTION_BYTES = 4_000;
const MAX_SCHEMA_NAME_BYTES = 128;

interface SchemaValidationState {
  nodes: number;
  properties: number;
  maxDepth: number;
}

function validateSchemaDefinition(schema: Record<string, unknown>, maxDepth: number): void {
  validateSchemaNode(schema, 0, { nodes: 0, properties: 0, maxDepth });
}

function validateSchemaNode(
  schema: Record<string, unknown>,
  depth: number,
  state: SchemaValidationState,
): void {
  if (depth > state.maxDepth) throw definitionError("Tool schema is too deeply nested");
  state.nodes += 1;
  if (state.nodes > MAX_SCHEMA_NODES) throw definitionError("Tool schema has too many nodes");
  if (schema.type !== undefined && !isTypeDeclaration(schema.type)) {
    throw definitionError("Tool schema type is invalid");
  }
  validateNumericBounds(schema);
  if (schema.description !== undefined
    && (typeof schema.description !== "string"
      || utf8ByteLength(schema.description) > MAX_SCHEMA_DESCRIPTION_BYTES)) {
    throw definitionError("Tool schema description is invalid");
  }
  validateSchemaEnum(schema.enum);

  if (schema.properties !== undefined) {
    const properties = schema.properties;
    if (!isRecord(properties)) throw definitionError("Object schema properties are invalid");
    const entries = Object.entries(properties);
    if (entries.length > MAX_SCHEMA_PROPERTIES) throw definitionError("Tool schema has too many properties");
    state.properties += entries.length;
    if (state.properties > MAX_SCHEMA_TOTAL_PROPERTIES) throw definitionError("Tool schema has too many properties");
    for (const [name, child] of entries) {
      if (!name || utf8ByteLength(name) > MAX_SCHEMA_NAME_BYTES || /[\u0000-\u001f\u007f]/.test(name)) {
        throw definitionError("Tool schema property name is invalid");
      }
      if (!isRecord(child)) throw definitionError(`Tool schema property ${name} is invalid`);
      validateSchemaNode(child, depth + 1, state);
    }
  }
  if (schema.required !== undefined
    && (!Array.isArray(schema.required)
      || schema.required.length > MAX_SCHEMA_REQUIRED
      || schema.required.some((name) => typeof name !== "string"))) {
    throw definitionError("Tool schema required list is invalid");
  }
  if (schema.additionalProperties !== undefined
    && typeof schema.additionalProperties !== "boolean"
    && !isRecord(schema.additionalProperties)) {
    throw definitionError("Tool schema additionalProperties is invalid");
  }
  if (isRecord(schema.additionalProperties)) {
    validateSchemaNode(schema.additionalProperties, depth + 1, state);
  }
  if (schema.items !== undefined) {
    if (Array.isArray(schema.items)) {
      if (schema.items.length > MAX_SCHEMA_PROPERTIES) {
        throw definitionError("Tool schema has too many tuple items");
      }
      for (const item of schema.items) {
        if (!isRecord(item)) throw definitionError("Tool schema tuple item is invalid");
        validateSchemaNode(item, depth + 1, state);
      }
    } else if (isRecord(schema.items)) {
      validateSchemaNode(schema.items, depth + 1, state);
    } else {
      throw definitionError("Tool schema items are invalid");
    }
  }
}

function validateNumericBounds(schema: Record<string, unknown>): void {
  if (schema.minimum === undefined && schema.maximum === undefined) return;
  if (schema.minimum !== undefined && !isFiniteNumber(schema.minimum)) {
    throw definitionError("Tool schema minimum is invalid");
  }
  if (schema.maximum !== undefined && !isFiniteNumber(schema.maximum)) {
    throw definitionError("Tool schema maximum is invalid");
  }
  if (schema.minimum !== undefined && schema.maximum !== undefined
    && (schema.minimum as number) > (schema.maximum as number)) {
    throw definitionError("Tool schema minimum exceeds maximum");
  }
}

function validateSchemaEnum(value: unknown): void {
  if (value === undefined) return;
  if (!Array.isArray(value) || value.length === 0 || value.length > MAX_SCHEMA_ENUM) {
    throw definitionError("Tool schema enum is invalid");
  }
}

function validateSchemaValue(schema: Record<string, unknown>, value: unknown, path: string): void {
  const types = schemaTypeNames(schema);
  if (types.length > 0 && !types.some((type) => matchesType(value, type))) {
    throw argumentError(`Invalid type for ${path}`);
  }
  if (Array.isArray(schema.enum) && !schema.enum.some((candidate) => Object.is(candidate, value))) {
    throw argumentError(`Invalid enum value for ${path}`);
  }
  if (types.some((type) => type === "number" || type === "integer") && typeof value === "number") {
    if (typeof schema.minimum === "number" && value < schema.minimum) {
      throw argumentError(`Value below minimum for ${path}`);
    }
    if (typeof schema.maximum === "number" && value > schema.maximum) {
      throw argumentError(`Value above maximum for ${path}`);
    }
  }
  const objectSchema = isRecord(value) && (
    types.includes("object")
    || schema.properties !== undefined
    || schema.required !== undefined
    || schema.additionalProperties !== undefined
  );
  if (objectSchema) {
    const object = value as Record<string, unknown>;
    const properties = isRecord(schema.properties) ? schema.properties : {};
    for (const key of (schema.required as string[] | undefined) ?? []) {
      if (!(key in object)) throw argumentError(`Missing required argument: ${path}.${key}`);
    }
    for (const [key, item] of Object.entries(object)) {
      const child = properties[key];
      if (!isRecord(child)) {
        if (schema.additionalProperties === false) throw argumentError(`Unknown tool argument: ${path}.${key}`);
        if (isRecord(schema.additionalProperties)) {
          validateSchemaValue(schema.additionalProperties, item, `${path}.${key}`);
        }
        continue;
      }
      validateSchemaValue(child, item, `${path}.${key}`);
    }
  } else if (Array.isArray(value) && (types.includes("array") || schema.items !== undefined)) {
    const items = schema.items;
    for (let index = 0; index < (value as unknown[]).length; index += 1) {
      const itemSchema = Array.isArray(items) ? items[index] : items;
      if (isRecord(itemSchema)) {
        validateSchemaValue(itemSchema, (value as unknown[])[index], `${path}[${index}]`);
      }
    }
  }
}

function isTypeDeclaration(value: unknown): boolean {
  return typeof value === "string"
    || (Array.isArray(value) && value.length > 0 && value.every((item) => typeof item === "string"));
}

function schemaTypeNames(schema: Record<string, unknown>): string[] {
  const value = schema.type;
  const candidates = typeof value === "string" ? [value] : Array.isArray(value) ? value : [];
  return candidates.filter((item): item is string => SCHEMA_TYPES.has(item));
}

function matchesType(value: unknown, expected: string): boolean {
  if (expected === "string") return typeof value === "string";
  if (expected === "number") return typeof value === "number" && Number.isFinite(value);
  if (expected === "integer") return typeof value === "number" && Number.isInteger(value);
  if (expected === "boolean") return typeof value === "boolean";
  if (expected === "array") return Array.isArray(value);
  if (expected === "object") return isRecord(value);
  if (expected === "null") return value === null;
  return false;
}

function isFiniteNumber(value: unknown): value is number {
  return typeof value === "number" && Number.isFinite(value);
}

function valueDepthExceeds(value: unknown, maxDepth: number): boolean {
  const pending: Array<{ value: unknown; depth: number }> = [{ value, depth: 0 }];
  while (pending.length > 0) {
    const current = pending.pop()!;
    if (current.depth > maxDepth) return true;
    if (current.value === null || typeof current.value !== "object") continue;
    const values = Array.isArray(current.value) ? current.value : Object.values(current.value);
    for (const child of values) pending.push({ value: child, depth: current.depth + 1 });
  }
  return false;
}

function argumentError(message: string): AgentError {
  return new AgentError("AGENT_TOOL_ARGUMENT_INVALID", message, { phase: "tool" });
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function cloneJSON<T>(value: T): T {
  return JSON.parse(JSON.stringify(value)) as T;
}
