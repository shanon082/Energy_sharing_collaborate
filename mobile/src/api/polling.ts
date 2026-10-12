/** Serialized foreground reads, bounded backoff, no replay of mutations. */
export class ForegroundPoller {
  private active = false;
  private disposed = false;
  private running = false;
  private failures = 0;
  private timer: ReturnType<typeof setTimeout> | undefined;
  private readonly read: () => Promise<boolean>;
  private readonly interval: number;
  private readonly maximum: number;
  private readonly schedule: typeof setTimeout;
  private readonly cancel: typeof clearTimeout;
  constructor(read: () => Promise<boolean>, interval = 15_000, maximum = 120_000,
    schedule = setTimeout, cancel = clearTimeout) {
    this.read = read; this.interval = interval; this.maximum = maximum;
    this.schedule = schedule; this.cancel = cancel;
  }

  setActive(active: boolean): void {
    if (this.disposed || this.active === active) return;
    this.active = active;
    if (this.timer !== undefined) this.cancel(this.timer);
    this.timer = undefined;
    if (active && !this.running) void this.tick();
  }

  private async tick(): Promise<void> {
    if (!this.active || this.disposed || this.running) return;
    this.running = true;
    try {
      this.failures = await this.read() ? 0 : this.failures + 1;
    } catch { this.failures += 1; }
    finally {
      this.running = false;
      if (this.active && !this.disposed) {
        this.timer = this.schedule(() => void this.tick(),
          Math.min(this.maximum, this.interval * 2 ** Math.min(this.failures, 8)));
      }
    }
  }

  dispose(): void {
    this.disposed = true; this.active = false;
    if (this.timer !== undefined) this.cancel(this.timer);
  }
}
