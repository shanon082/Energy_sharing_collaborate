/** Prevent an older read from replacing newer data or a cleared account view. */
export class LatestRead {
  private generation = 0;
  begin(): number { return ++this.generation; }
  current(ticket: number): boolean { return ticket === this.generation; }
  invalidate(): void { this.generation++; }
}
