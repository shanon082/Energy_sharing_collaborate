'use client';
import { useEffect, useState, useTransition } from 'react';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { Form, FormField, FormItem, FormLabel, FormControl, FormMessage } from '@/components/ui/form';
import { Input } from '@/components/ui/input';
import { Button } from '@/components/ui/button';
import { FormError } from '@/components/common/form-error';
import { FormSuccess } from '@/components/common/form-success';
import { login } from '../login';
import { verify2FA } from '../verify2fa';
import { resendVerificationEmail } from '../../resend';
import { LoginSchema } from '@/lib/schema';
import { useRouter, useSearchParams } from 'next/navigation';
import CardWrapper from '@/components/common/card-wrapper';
import Link from 'next/link';
import { z } from 'zod';
import { Shield, Eye, EyeOff } from 'lucide-react';

export default function LoginForm() {
  const searchParams = useSearchParams();
  const router = useRouter();
  const [error, setError] = useState<string>('');
  const [success, setSuccess] = useState<string>('');
  const [showResend, setShowResend] = useState(false);
  const [emailForResend, setEmailForResend] = useState('');
  const [isPending, startTransition] = useTransition();

  // 2FA challenge state
  const [challengeToken, setChallengeToken] = useState<string | null>(null);
  const [totpCode, setTotpCode] = useState('');
  const [totpLoading, setTotpLoading] = useState(false);
  const [staffEmail, setStaffEmail] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [rememberMe, setRememberMe] = useState(false);

  useEffect(() => {
    if (searchParams.get('session') === 'expired') {
      setError('Your session expired. Please sign in again.');
    }
  }, [searchParams]);

  const form = useForm<z.infer<typeof LoginSchema>>({
    resolver: zodResolver(LoginSchema),
    defaultValues: { email: '', password: '' },
  });

  useEffect(() => {
    if (searchParams.get('verified') === '1') {
      setSuccess('Email verified successfully. Please log in.');
    }
  }, [searchParams]);


  async function onSubmit(values: z.infer<typeof LoginSchema>) {
    setError('');
    setSuccess('');
    setShowResend(false);

    const result = await login(values, rememberMe);

    if ('requires_2fa' in result && result.requires_2fa) {
      // Staff member — show TOTP challenge
      setChallengeToken(result.challenge_token ?? null);
      setStaffEmail(result.user?.email ?? values.email);
      setRememberMe(result.rememberMe ?? rememberMe);
      return;
    }

    if ('success' in result && result.success) {
      const dest =
        (result.must_change_password || result.user?.must_change_password) && !result.isAdmin
          ? '/change-password'
          : (result.redirectTo || '/dashboard');
      window.location.href = dest;
    } else if (result.error === 'EMAIL_NOT_VERIFIED') {
      setError(result.message || 'Please verify your email first');
      setShowResend(true);
      setEmailForResend(values.email);
    } else {
      setError(result.message || 'Wrong credentials. Please try again.');
    }
  }

  async function onVerify2FA() {
    if (!challengeToken || totpCode.length !== 6) return;
    setTotpLoading(true);
    setError('');
    try {
      const result = await verify2FA(challengeToken, totpCode, rememberMe);
      if (result.success) {
        window.location.href = result.redirectTo || '/admin/dashboard';
      } else {
        setError(result.error || 'Invalid code. Try again.');
        setTotpCode('');
      }
    } finally {
      setTotpLoading(false);
    }
  }

  const handleResendVerification = async () => {
    if (!emailForResend) return;
    const result = await resendVerificationEmail(emailForResend);
    if (result.success) {
      setError('Verification email sent. Please check your inbox.');
      setShowResend(false);
    } else {
      setError(result.error || 'Failed to resend verification email');
    }
  };

  // ── 2FA challenge screen ──
  if (challengeToken) {
    return (
      <CardWrapper title="Two-Factor Authentication" variant="auth">
        <div className="space-y-6">
          <div className="flex flex-col items-center gap-3 text-center">
            <div className="w-12 h-12 rounded-full bg-primary/10 flex items-center justify-center">
              <Shield className="h-6 w-6 text-primary" />
            </div>
            <div>
              <p className="font-medium">Verification required</p>
              <p className="text-sm text-muted-foreground mt-1">
                Enter the 6-digit code from your Google Authenticator app
                {staffEmail && <span> for <strong>{staffEmail}</strong></span>}.
              </p>
            </div>
          </div>

          <div className="space-y-3">
            <Input
              placeholder="000000"
              maxLength={6}
              className="text-center font-mono text-2xl tracking-[0.5em] h-14"
              value={totpCode}
              onChange={(e) => setTotpCode(e.target.value.replace(/\D/g, ''))}
              onKeyDown={(e) => e.key === 'Enter' && onVerify2FA()}
              autoFocus
            />
            <FormError message={error} />
            <Button
              className="w-full"
              onClick={onVerify2FA}
              disabled={totpLoading || totpCode.length !== 6}
            >
              {totpLoading ? 'Verifying…' : 'Verify'}
            </Button>
            <Button
              variant="ghost"
              className="w-full text-sm"
              onClick={() => {
                setChallengeToken(null);
                setTotpCode('');
                setError('');
              }}
            >
              ← Back to login
            </Button>
          </div>

          <p className="text-xs text-muted-foreground text-center">
            Lost access to your authenticator? Contact your Admin to reset 2FA.
          </p>
        </div>
      </CardWrapper>
    );
  }

  // ── Normal login screen ──
  return (
    <CardWrapper title="Sign in to your account" variant="auth">
      <p className="mb-4 text-sm text-muted-foreground">
        New here?{" "}
        <Link href="/auth/register" className="font-medium text-indigo-600 hover:text-indigo-500">
          Create your own account
        </Link>
        . Admin-provisioned users: use your email and temporary password <strong>1234</strong>, then set a new password.
      </p>
      <Form {...form}>
        <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-6" autoComplete="on">
          <FormField
            control={form.control}
            name="email"
            render={({ field }) => (
              <FormItem>
                <FormLabel>Email</FormLabel>
                <FormControl>
                  <Input
                    disabled={isPending}
                    type="email"
                    autoComplete="username email"
                    placeholder="johndoe@example.com"
                    {...field}
                  />
                </FormControl>
                <FormMessage />
              </FormItem>
            )}
          />
          <FormField
            control={form.control}
            name="password"
            render={({ field }) => (
              <FormItem>
                <FormLabel>Password</FormLabel>
                <FormControl>
                  <div className="relative">
                    <Input
                      disabled={isPending}
                      type={showPassword ? 'text' : 'password'}
                      autoComplete="current-password"
                      placeholder="Password"
                      className="pr-10"
                      {...field}
                    />
                    <Button
                      type="button"
                      variant="ghost"
                      size="icon"
                      className="absolute right-0 top-0 h-full px-3 hover:bg-transparent"
                      onClick={() => setShowPassword((prev) => !prev)}
                      tabIndex={-1}
                      aria-label={showPassword ? 'Hide password' : 'Show password'}
                    >
                      {showPassword ? (
                        <EyeOff className="h-4 w-4 text-muted-foreground" />
                      ) : (
                        <Eye className="h-4 w-4 text-muted-foreground" />
                      )}
                    </Button>
                  </div>
                </FormControl>
                <FormMessage />
              </FormItem>
            )}
          />
          <div className="flex items-center justify-between">
            <div className="flex items-center">
              <input
                id="remember-me"
                name="remember-me"
                type="checkbox"
                checked={rememberMe}
                onChange={(e) => setRememberMe(e.target.checked)}
                className="h-4 w-4 text-indigo-600 focus:ring-indigo-500 border-gray-300 rounded"
              />
              <label htmlFor="remember-me" className="ml-2 block text-sm text-gray-900 dark:text-gray-300">
                Remember me on this device
              </label>
            </div>
            <div className="text-sm">
              <Link href="/auth/forgot-password" className="font-medium text-indigo-600 hover:text-indigo-500">
                Forgot your password?
              </Link>
            </div>
          </div>
          <FormError message={error} />
          <FormSuccess message={success} />
          <Button type="submit" disabled={isPending} className="w-full text-white dark:text-gray-900 bg-sky-500 dark:bg-white">
            Login
          </Button>
        </form>
      </Form>
      {error && showResend && (
        <div className="mt-3">
          <Button onClick={handleResendVerification} className="ml-2 text-blue-600" variant="link">
            Resend verification email
          </Button>
        </div>
      )}
    </CardWrapper>
  );
}
