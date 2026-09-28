export type VerifyResponse =
  | { success: true; message: string }
  | { success: false; error: string };
