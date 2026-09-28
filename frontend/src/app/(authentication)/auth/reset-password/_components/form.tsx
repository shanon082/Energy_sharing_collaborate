"use client";

import { useEffect, useState, useTransition } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { useRouter } from "next/navigation";
import {
  Form,
  FormField,
  FormItem,
  FormLabel,
  FormControl,
  FormMessage,
  FormDescription,
} from "@/components/ui/form";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { FormError } from "@/components/common/form-error";
import { FormSuccess } from "@/components/common/form-success";
import { validateResetLink, resetPassword } from "../reset";
import { z } from "zod";
import { ResetPasswordSchema } from "@/lib/schema";
import CardWrapper from "@/components/common/card-wrapper";
import { getApiErrorMessage } from "@/lib/api-response";
import { Eye, EyeOff } from "lucide-react";

type ResetPasswordFormData = z.infer<typeof ResetPasswordSchema>;

export default function ResetPasswordForm({
  uid,
  token,
}: {
  uid: string;
  token: string;
}) {
  const [error, setError] = useState<string>("");
  const [success, setSuccess] = useState<string>("");
  const [isValid, setIsValid] = useState<boolean | null>(null);
  const [isPending, startTransition] = useTransition();
  const [isValidating, setIsValidating] = useState(true);
  const [showPassword, setShowPassword] = useState(false);
  const [showConfirmPassword, setShowConfirmPassword] = useState(false);
  const router = useRouter();

  const form = useForm<ResetPasswordFormData>({
    resolver: zodResolver(ResetPasswordSchema),
    defaultValues: { password: "", confirm_password: "" },
    mode: "onTouched",
  });

  useEffect(() => {
    validateResetLink(uid, token)
      .then((data) => {
        setIsValidating(false);
        if (data.error) {
          setError(
            getApiErrorMessage(data.error, "Invalid or expired reset link")
          );
          setIsValid(false);
        } else {
          setIsValid(true);
        }
      })
      .catch(() => {
        setIsValidating(false);
        setError("Network error validating link");
        setIsValid(false);
      });
  }, [uid, token]);

  const onSubmit = (values: ResetPasswordFormData) => {
    setError("");
    setSuccess("");
    startTransition(async () => {
      try {
        const result = await resetPassword(uid, token, values);
        if (result.error) {
          setError(getApiErrorMessage(result.error, "Failed to reset password"));
          return;
        }

        setSuccess(result.success || "Password reset successfully!");
        form.reset();
        setTimeout(() => router.replace(result.redirectTo!), 1500);
      } catch {
        setError("Something went wrong. Please try again.");
      }
    });
  };

  const onInvalid = () => {
    const firstError =
      form.formState.errors.password?.message ||
      form.formState.errors.confirm_password?.message;
    if (firstError) {
      setError(String(firstError));
    }
  };

  if (isValidating) {
    return (
      <CardWrapper title="Reset Password" variant="auth">
        <div className="flex items-center justify-center py-8">
          Validating reset link...
        </div>
      </CardWrapper>
    );
  }

  if (!isValid) {
    return (
      <CardWrapper title="Reset Password" variant="auth">
        <div className="text-center py-8 text-destructive">
          {error || "Invalid or expired reset link. Please request a new one."}
        </div>
        <Button
          type="button"
          onClick={() => router.push("/auth/forgot-password")}
          className="w-full"
        >
          Request New Link
        </Button>
      </CardWrapper>
    );
  }

  return (
    <CardWrapper
      title="Reset Password"
      subtitle="Choose a new password. You can paste the same value into both fields to confirm."
      variant="auth"
    >
      <Form {...form}>
        <form
          onSubmit={form.handleSubmit(onSubmit, onInvalid)}
          className="space-y-4 sm:space-y-6"
        >
          <FormField
            control={form.control}
            name="password"
            render={({ field }) => (
              <FormItem>
                <FormLabel>New Password</FormLabel>
                <FormControl>
                  <div className="relative">
                    <Input
                      type={showPassword ? "text" : "password"}
                      autoComplete="new-password"
                      placeholder="Enter new password"
                      disabled={isPending}
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
                      aria-label={showPassword ? "Hide password" : "Show password"}
                    >
                      {showPassword ? (
                        <EyeOff className="h-4 w-4 text-muted-foreground" />
                      ) : (
                        <Eye className="h-4 w-4 text-muted-foreground" />
                      )}
                    </Button>
                  </div>
                </FormControl>
                <FormDescription>
                  At least 12 characters with uppercase, lowercase, and a number.
                </FormDescription>
                <FormMessage />
              </FormItem>
            )}
          />
          <FormField
            control={form.control}
            name="confirm_password"
            render={({ field }) => (
              <FormItem>
                <FormLabel>Confirm Password</FormLabel>
                <FormControl>
                  <div className="relative">
                    <Input
                      type={showConfirmPassword ? "text" : "password"}
                      autoComplete="new-password"
                      placeholder="Re-enter new password"
                      disabled={isPending}
                      className="pr-10"
                      {...field}
                    />
                    <Button
                      type="button"
                      variant="ghost"
                      size="icon"
                      className="absolute right-0 top-0 h-full px-3 hover:bg-transparent"
                      onClick={() => setShowConfirmPassword((prev) => !prev)}
                      tabIndex={-1}
                      aria-label={
                        showConfirmPassword ? "Hide password" : "Show password"
                      }
                    >
                      {showConfirmPassword ? (
                        <EyeOff className="h-4 w-4 text-muted-foreground" />
                      ) : (
                        <Eye className="h-4 w-4 text-muted-foreground" />
                      )}
                    </Button>
                  </div>
                </FormControl>
                <p className="text-xs text-muted-foreground">
                  Copy and paste from New Password is supported here.
                </p>
                <FormMessage />
              </FormItem>
            )}
          />
          <FormError message={error} />
          <FormSuccess message={success} />
          <Button
            type="submit"
            disabled={isPending}
            className="w-full text-white dark:text-gray-900 bg-sky-600 hover:bg-sky-700 dark:bg-sky-500"
          >
            {isPending ? "Resetting..." : "Reset Password"}
          </Button>
        </form>
      </Form>
    </CardWrapper>
  );
}
