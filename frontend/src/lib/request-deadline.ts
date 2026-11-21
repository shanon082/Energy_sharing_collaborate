/** Bound loading states, including stalled JSON bodies. Timeout is NOT failure
 * evidence for a financial mutation; callers retain the durable recovery ID. */
export class RequestTimeout extends Error {
  constructor() { super('The request timed out. Its stored payment outcome may still be pending; refresh to recover it.'); }
}
export async function withRequestDeadline<T>(work: (signal: AbortSignal) => Promise<T>, milliseconds = 20000): Promise<T> {
  const controller = new AbortController();
  let timer: ReturnType<typeof setTimeout> | undefined;
  const timeout = new Promise<never>((_, reject) => {
    timer = setTimeout(() => { reject(new RequestTimeout()); controller.abort(); }, milliseconds);
  });
  try { return await Promise.race([work(controller.signal), timeout]); }
  finally { clearTimeout(timer); }
}
