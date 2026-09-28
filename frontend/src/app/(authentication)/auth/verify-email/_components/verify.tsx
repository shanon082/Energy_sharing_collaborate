'use client';

import { useState, useEffect } from 'react';
import { useParams, useSearchParams } from 'next/navigation';
import { clearAuthSession, verifyEmail } from '../../../../ck/verify/email/verify';
import { useParams, useSearchParams, useRouter } from 'next/navigation';
import { CheckCircle2, XCircle, Loader2, Mail } from 'lucide-react';
import { verifyEmail } from '../../../../ck/verify/email/verify';
import { resendVerificationEmail } from '../../resend';
import { Button } from '@/components/ui/button';
import { GpawaLogo, LOGO_SIZES } from '@/components/common/gpawa-logo';

const asString = (value: string | string[] | undefined): string | undefined =>
  typeof value === 'string' ? value : undefined;

export default function VerifyEmail({ uid: propUid, token: propToken }: { uid?: string; token?: string } = {}) {
  const searchParams = useSearchParams();
  const params = useParams();
  const router = useRouter();

  const uid   = propUid   || asString(params?.uid)   || searchParams.get('uid')   || undefined;
  const token = propToken || asString(params?.token) || searchParams.get('token') || undefined;
  const email = searchParams.get('email') || undefined;

  const [status, setStatus]   = useState<'idle' | 'verifying' | 'success' | 'error' | 'resending'>('idle');
  const [message, setMessage] = useState('');
  const [showResend, setShowResend] = useState(false);

  useEffect(() => {
    if (uid && token) {
      handleVerify();
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function handleVerify() {
    if (!uid || !token) {
      setStatus('error');
      setMessage('Missing verification parameters — please use the link from your email.');
      return;
    }
    setStatus('verifying');
    try {
      const result = await verifyEmail(uid, token);
      if (result.success) {
        await clearAuthSession();
        setStatus('success');
        setMessage(result.message || 'Email verified successfully');
        // Redirect after a delay
        setTimeout(() => {
          window.location.href = '/auth/login?verified=1';
        }, 3000);
      } else {
        setStatus('error');
        setMessage(result.error || 'Invalid or expired verification link.');
        setShowResend(true);
      }
    } catch {
      setStatus('error');
      setMessage('An unexpected error occurred during verification.');
      setShowResend(true);
    }
  }

  async function handleResend() {
    if (!email) {
      setMessage('No email address available. Please register again.');
      return;
    }
    setStatus('resending');
    try {
      const result = await resendVerificationEmail(email);
      if (result.success) {
        setStatus('success');
        setMessage(result.message || 'Verification email resent — check your inbox (and spam folder).');
      } else {
        setStatus('error');
        setMessage(result.error || 'Failed to resend verification email.');
      }
    } catch {
      setStatus('error');
      setMessage('Failed to resend verification email.');
    }
  }

  return (
    <div className="min-h-screen flex flex-col items-center justify-center bg-gray-50 dark:bg-slate-950 px-4">
      <div className="w-full max-w-sm bg-white dark:bg-slate-900 rounded-2xl shadow-xl border border-gray-200/80 dark:border-slate-800 p-8 space-y-6 text-center">
        <GpawaLogo
          href="/"
          textSize={LOGO_SIZES.header.textSize}
          logoSize={LOGO_SIZES.header.logoSize}
          className="justify-center"
        />

        <h1 className="text-xl font-bold text-gray-900 dark:text-white">Email Verification</h1>

        {status === 'verifying' && (
          <div className="flex flex-col items-center gap-3 py-4">
            <Loader2 className="h-10 w-10 animate-spin text-primary" />
            <p className="text-sm text-muted-foreground">Verifying your email address…</p>
          </div>
        )}

        {status === 'resending' && (
          <div className="flex flex-col items-center gap-3 py-4">
            <Loader2 className="h-10 w-10 animate-spin text-primary" />
            <p className="text-sm text-muted-foreground">Sending verification email…</p>
          </div>
        )}

        {status === 'success' && (
          <div className="flex flex-col items-center gap-3 py-2">
            <CheckCircle2 className="h-12 w-12 text-green-500" />
            <p className="text-green-700 dark:text-green-400 font-medium">{message}</p>
            <p className="text-sm text-muted-foreground">Redirecting to login…</p>
            <Button
              onClick={() => router.push('/auth/login')}
              className="w-full gpawa-gradient text-white mt-2"
            >
              Go to Login now
            </Button>
          </div>
        )}

        {status === 'error' && (
          <div className="flex flex-col items-center gap-3 py-2">
            <XCircle className="h-12 w-12 text-destructive" />
            <p className="text-destructive text-sm">{message}</p>
            {showResend && email && (
              <Button onClick={handleResend} className="w-full mt-2">
                Resend Verification Email
              </Button>
            )}
            <Button variant="outline" onClick={() => router.push('/auth/login')} className="w-full">
              Back to Login
            </Button>
          </div>
        )}

        {status === 'idle' && !uid && (
          <div className="flex flex-col items-center gap-3 py-2">
            <Mail className="h-12 w-12 text-blue-500" />
            <p className="text-sm text-gray-600 dark:text-gray-300">
              {email
                ? <>Check your inbox at <strong>{email}</strong> for the verification link. Also check your spam folder.</>
                : 'Please check your email for a verification link.'}
            </p>
            {email && (
              <Button onClick={handleResend} variant="outline" className="w-full">
                Resend Verification Email
              </Button>
            )}
            <Button variant="ghost" onClick={() => router.push('/auth/login')} className="w-full text-sm">
              Already verified? Sign in
            </Button>
          </div>
        )}
      </div>
    </div>
  );
}
