import { AgentError } from "./errors";

export interface CancellationToken {
  readonly cancelled: boolean;
  readonly reason?: string;
  throwIfCancelled(): void;
  onCancel(handler: (reason?: string) => void): () => void;
}

export class AgentCancelledError extends AgentError {
  constructor(reason?: string) {
    super("AGENT_CANCELLED", reason || "Agent operation cancelled", {
      phase: "transport",
    });
    this.name = "AgentCancelledError";
  }
}

class MutableCancellationToken implements CancellationToken {
  private handlers = new Set<(reason?: string) => void>();
  private cancelledValue = false;
  private reasonValue?: string;

  get cancelled(): boolean {
    return this.cancelledValue;
  }

  get reason(): string | undefined {
    return this.reasonValue;
  }

  throwIfCancelled(): void {
    if (this.cancelledValue) throw new AgentCancelledError(this.reasonValue);
  }

  onCancel(handler: (reason?: string) => void): () => void {
    if (this.cancelledValue) {
      handler(this.reasonValue);
      return () => undefined;
    }
    this.handlers.add(handler);
    let subscribed = true;
    return () => {
      if (!subscribed) return;
      subscribed = false;
      this.handlers.delete(handler);
    };
  }

  cancel(reason?: string): void {
    if (this.cancelledValue) return;
    this.cancelledValue = true;
    this.reasonValue = reason;
    const handlers = Array.from(this.handlers);
    this.handlers.clear();
    for (const handler of handlers) handler(reason);
  }
}

export class CancellationTokenSource {
  private readonly mutableToken = new MutableCancellationToken();
  readonly token: CancellationToken = this.mutableToken;

  cancel(reason?: string): void {
    this.mutableToken.cancel(reason);
  }
}

export const uncancelledToken: CancellationToken = {
  cancelled: false,
  throwIfCancelled(): void {},
  onCancel(): () => void { return () => undefined; },
};
