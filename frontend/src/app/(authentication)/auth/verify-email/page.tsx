'use client';

import { useEffect, useState } from 'react';
import { useSearchParams } from 'next/navigation';
import { clearAuthSession, verifyEmail } from '../../../ck/verify/email/verify';
import { resendVerificationEmail } from '../resend';

export default function VerifyEmailPage() {
  const searchParams = useSearchParams();
  const uid = searchParams.get('uid');
  const token = searchParams.get('token');
  const email = searchParams.get('email');
  
  const [status, setStatus] = useState<'idle' | 'verifying' | 'success' | 'error' | 'resending'>('idle');
  const [message, setMessage] = useState('');
  const [showResend, setShowResend] = useState(false);
  const isResending = status === 'resending';

  useEffect(() => {
    // Only auto-verify if we have both uid and token
    if (uid && token) {
      handleVerifyEmail();
    } else if (email) {
      // If we only have email, show message to check inbox
      setStatus('idle');
      setMessage(`Please check your email (${email}) for the verification link.`);
    }
  }, [uid, token, email]);

  const handleVerifyEmail = async () => {
    if (!uid || !token) {
      setStatus('error');
      setMessage('Missing verification parameters');
      return;
    }
    
    setStatus('verifying');
    try {
      const result = await verifyEmail(uid, token);
      
      if (result.success) {
        await clearAuthSession();
        setStatus('success');
        setMessage(result.message);
        // Redirect after a delay
        setTimeout(() => {
          window.location.href = '/auth/login?verified=1';
        }, 3000);
      } else {
        setStatus('error');
        setMessage(result.error);
        setShowResend(true);
      }
    } catch (error) {
      setStatus('error');
      setMessage('An unexpected error occurred during verification');
      setShowResend(true);
    }
  };

  const handleResendEmail = async () => {
    if (!email) {
      setMessage('No email address available for resending');
      return;
    }
    
    setStatus('resending');
    try {
      const result = await resendVerificationEmail(email);
      
      if (result.success) {
        setStatus('success');
        setMessage(result.message);
      } else {
        setStatus('error');
        setMessage(result.error);
      }
    } catch (error) {
      setStatus('error');
      setMessage('Failed to resend verification email');
    }
  };

  return (
    <div className="min-h-screen overflow-hidden bg-gradient-to-br from-blue-50 via-emerald-50 to-blue-100 dark:from-blue-950 dark:via-emerald-900/20 dark:to-blue-900">
      <div className="min-h-screen flex items-start justify-center px-3 py-6 sm:items-center sm:px-4 sm:py-8">
        <div className="w-full max-w-md">
          <h2 className="text-center text-2xl font-bold tracking-tight text-gray-900 dark:text-white sm:text-3xl">
            Email Verification
          </h2>
          <div className="mt-5 bg-white/95 dark:bg-slate-900/90 backdrop-blur-sm py-6 px-4 shadow-xl shadow-blue-500/10 rounded-2xl sm:mt-6 sm:px-10 border border-gray-200/70 dark:border-slate-800/70 max-h-[85vh] overflow-y-auto">
          {status === 'verifying' && (
            <div className="text-center">
              <p>Verifying your email address...</p>
            </div>
          )}

          {status === 'resending' && (
            <div className="text-center">
              <p>Resending verification email...</p>
            </div>
          )}
          
          {status === 'success' && (
            <div className="text-center text-green-600">
              <p>{message}</p>
              <p>Redirecting to login page...</p>
            </div>
          )}
          
          {status === 'error' && (
            <div className="text-center text-red-600">
              <p>{message}</p>
              {showResend && email && (
                <button
                  onClick={handleResendEmail}
                  disabled={isResending}
                  className="mt-4 px-4 py-2 bg-blue-600 text-white rounded disabled:bg-gray-400"
                >
                  {isResending ? 'Sending...' : 'Resend Verification Email'}
                </button>
              )}
            </div>
          )}
          
          {(status === 'idle' || (!uid && !token)) && (
            <div className="text-center">
              <p>{message || 'Please check your email for a verification link.'}</p>
              {email && (
                <>
                  <p className="mt-2">Sent to: {email}</p>
                  <button
                    onClick={handleResendEmail}
                    disabled={isResending}
                    className="mt-4 px-4 py-2 bg-blue-600 text-white rounded disabled:bg-gray-400"
                  >
                    {isResending ? 'Sending...' : 'Resend Verification Email'}
                  </button>
                </>
              )}
            </div>
          )}
          </div>
        </div>
      </div>
    </div>
  );
}
