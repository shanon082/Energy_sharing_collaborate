"use server";

// lib/verify-email.ts
import { AUTHENTICATION_COOKIE, AUTHENTICATION_REFRESH_COOKIE, VERIFICATION_EMAIL } from "@/common/constants/auth-cookie";
import { get } from "../../../../lib/fetch";
import { getApiErrorMessage } from "../../../../lib/api-response";
import { VerifyResponse } from "../../../../lib/verify-response";
import { cookies } from "next/headers";

export async function clearAuthSession() {
  const cookieStore = await cookies();
  cookieStore.delete(AUTHENTICATION_COOKIE);
  cookieStore.delete(AUTHENTICATION_REFRESH_COOKIE);
  cookieStore.delete(VERIFICATION_EMAIL);
}

export async function verifyEmail(uid: string, token: string): Promise<VerifyResponse> {
  try {
    // Decode the uid first to handle any double encoding
    const decodedUid = decodeURIComponent(uid);
    
    const response = await get(`auth/verify-email/?uid=${encodeURIComponent(decodedUid)}&token=${encodeURIComponent(token)}`);
    
    if (response.error) {
      return { 
        success: false, 
        error: getApiErrorMessage(response.error, 'Invalid or expired verification link')
      };
    }

    return { 
      success: true, 
      message: 'Email verified successfully' 
    };
  } catch {
    return { 
      success: false, 
      error: 'Server error occurred during verification' 
    };
  }
}
