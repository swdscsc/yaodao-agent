import { normalizeConfigFrame, type NormalizedSessionConfig } from "./schema";

const KEY_PREFIX = "listenai.voice.config.";

export interface SessionConfigStore {
  replace(sessionId: string, frame: unknown): NormalizedSessionConfig;
  get(sessionId: string): NormalizedSessionConfig | null;
  acquire(sessionId: string): SessionConfigLease | null;
  clear(sessionId: string): void;
}

export interface SessionConfigLease {
  config: NormalizedSessionConfig;
  release(): void;
}

interface ConfigGeneration {
  config: NormalizedSessionConfig;
  secretKeys: string[];
  leases: number;
  retired: boolean;
}

export type ConfigWarningObserver = (sessionId: string, code: string) => void;

export class HostSessionConfigStore implements SessionConfigStore {
  private generationCounter = 0;
  private readonly current = new Map<string, ConfigGeneration>();
  private readonly generations = new Map<string, Set<ConfigGeneration>>();

  constructor(private readonly onWarning?: ConfigWarningObserver) {}

  replace(sessionId: string, frame: unknown): NormalizedSessionConfig {
    const generation = ++this.generationCounter;
    const namespace = `config.g${generation}`;
    let normalized;
    try {
      normalized = normalizeConfigFrame(frame, namespace);
    } catch (error) {
      this.clear(sessionId);
      throw error;
    }
    const keys = Object.keys(normalized.secrets);
    try {
      for (const [key, value] of Object.entries(normalized.secrets)) {
        host.secretSet(sessionId, key, value);
      }
      host.kvSet(sessionConfigKey(sessionId), JSON.stringify(normalized.publicConfig), null);
    } catch (error) {
      for (const key of keys) host.secretDelete(sessionId, key);
      this.clear(sessionId);
      throw error;
    }
    const state: ConfigGeneration = {
      config: normalized.publicConfig,
      secretKeys: keys,
      leases: 0,
      retired: false,
    };
    const generations = this.generations.get(sessionId) ?? new Set<ConfigGeneration>();
    generations.add(state);
    this.generations.set(sessionId, generations);
    const previous = this.current.get(sessionId);
    this.current.set(sessionId, state);
    if (previous) this.retire(sessionId, previous);
    this.emitWarnings(sessionId, normalized.warnings);
    return normalized.publicConfig;
  }

  get(sessionId: string): NormalizedSessionConfig | null {
    const current = this.current.get(sessionId);
    if (current) return current.config;
    const value = host.kvGet(sessionConfigKey(sessionId));
    if (!value) return null;
    try {
      return JSON.parse(value) as NormalizedSessionConfig;
    } catch {
      return null;
    }
  }

  acquire(sessionId: string): SessionConfigLease | null {
    const generation = this.current.get(sessionId);
    if (!generation || generation.retired) return null;
    generation.leases += 1;
    let released = false;
    return {
      config: generation.config,
      release: () => {
        if (released) return;
        released = true;
        generation.leases = Math.max(0, generation.leases - 1);
        if (generation.retired) this.deleteGeneration(sessionId, generation);
      },
    };
  }

  clear(sessionId: string): void {
    host.kvSet(sessionConfigKey(sessionId), "", null);
    this.current.delete(sessionId);
    for (const generation of Array.from(this.generations.get(sessionId) ?? [])) {
      this.retire(sessionId, generation);
    }
  }

  private retire(sessionId: string, generation: ConfigGeneration): void {
    generation.retired = true;
    if (generation.leases === 0) this.deleteGeneration(sessionId, generation);
  }

  private deleteGeneration(sessionId: string, generation: ConfigGeneration): void {
    for (const key of generation.secretKeys) host.secretDelete(sessionId, key);
    const generations = this.generations.get(sessionId);
    generations?.delete(generation);
    if (generations?.size === 0) this.generations.delete(sessionId);
  }

  private emitWarnings(sessionId: string, warnings: string[]): void {
    if (!this.onWarning) return;
    for (const warning of warnings) {
      try {
        this.onWarning(sessionId, warning);
      } catch {
        // Observability must not invalidate an otherwise safe config replacement.
      }
    }
  }
}

export function sessionConfigKey(sessionId: string): string {
  return `${KEY_PREFIX}${sessionId}`;
}
