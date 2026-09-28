// app/auth/verify-email/_actions/resend.ts
'use server';

import { get } from '@/lib/fetch';
import { getApiErrorMessage } from '@/lib/api-response';
import { VerifyResponse } from '@/lib/verify-response';

export async function resendVerificationEmail(email: string): Promise<VerifyResponse> {
  if (!email) {
    return { success: false, error: 'Email is required' };
  }
  
  try {
    const response = await get(`auth/resend-email-link/?email=${encodeURIComponent(email)}`);
    
    if (response.error) {
      return { 
        success: false,
        error: getApiErrorMessage(response.error, 'Failed to resend verification email') 
      };
    }
    
    return { 
      success: true,
      message: 'Verification email sent successfully. Please check your inbox.' 
    };
  } catch (error) {
    console.error('Resend verification error:', error);
    return { success: false, error: 'Server error occurred while resending verification email' };
  }
}
