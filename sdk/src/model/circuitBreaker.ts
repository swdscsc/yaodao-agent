import { AgentError } from "../runtime/errors";

export interface ModelCircuitBreaker {
  beforeRequest(): void;
  recordSuccess(): void;
  recordFailure(): void;
}

export interface KVBackedCircuitBreakerOptions {
  key: string;
  failureThreshold?: number;
  cooldownMs?: number;
  now?: () => number;
}

interface CircuitState {
  failures: number;
  openUntil: number;
}

export class KVBackedCircuitBreaker implements ModelCircuitBreaker {
  private readonly key: string;
  private readonly failureThreshold: number;
  private readonly cooldownMs: number;
  private readonly now: () => number;

  constructor(options: KVBackedCircuitBreakerOptions) {
    this.key = options.key;
    this.failureThreshold = options.failureThreshold ?? 3;
    this.cooldownMs = options.cooldownMs ?? 30_000;
    this.now = options.now ?? Date.now;
    if (!this.key || this.key.length > 128 || this.failureThreshold < 1 || this.cooldownMs < 1) {
      throw new AgentError("AGENT_MODEL_CONFIG_INVALID", "Invalid circuit breaker configuration", {
        phase: "config",
      });
    }
  }

  beforeRequest(): void {
    const state = this.read();
    if (state.openUntil > this.now()) {
      throw new AgentError("AGENT_MODEL_CIRCUIT_OPEN", "Custom model circuit is open", {
        retryable: true,
        phase: "model",
      });
    }
  }

  recordSuccess(): void {
    host.kvSet(this.key, "", 1);
  }

  recordFailure(): void {
    const now = this.now();
    const current = this.read();
    const failures = current.openUntil > 0 && current.openUntil <= now
      ? 1
      : current.failures + 1;
    const state: CircuitState = {
      failures,
      openUntil: failures >= this.failureThreshold ? now + this.cooldownMs : 0,
    };
    const ttlSeconds = Math.max(2, Math.ceil((this.cooldownMs * 2) / 1000));
    host.kvSet(this.key, JSON.stringify(state), ttlSeconds);
  }

  private read(): CircuitState {
    const raw = host.kvGet(this.key);
    if (!raw) return { failures: 0, openUntil: 0 };
    try {
      const value = JSON.parse(raw) as Record<string, unknown>;
      return {
        failures: typeof value.failures === "number" && value.failures >= 0 ? value.failures : 0,
        openUntil: typeof value.openUntil === "number" && value.openUntil >= 0 ? value.openUntil : 0,
      };
    } catch {
      return { failures: 0, openUntil: 0 };
    }
  }
}

export function customModelCircuitKey(baseUrl: string, model: string): string {
  const normalized = `${baseUrl.trim().replace(/\/+$/, "").toLowerCase()}\u0000${model.trim()}`;
  let hash = 2166136261;
  for (let index = 0; index < normalized.length; index += 1) {
    hash ^= normalized.charCodeAt(index);
    hash = Math.imul(hash, 16777619);
  }
  return `agent.model-circuit.${(hash >>> 0).toString(36)}`;
}
