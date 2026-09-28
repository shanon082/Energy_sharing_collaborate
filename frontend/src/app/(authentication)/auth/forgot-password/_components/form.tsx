"use client"
import type { z } from "zod"
import { zodResolver } from "@hookform/resolvers/zod"
import { useState, useTransition } from "react";
import 'react-phone-number-input/style.css'   
import {
  Form,
  FormControl,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from "@/components/ui/form"
import { Input } from "@/components/anim/input";
import { ForgotPasswordSchema } from "@/lib/schema";
import { useForm } from "react-hook-form";
import { Button } from "@/components/ui/button";
import { FormError } from "@/components/common/form-error";
import { FormSuccess } from "@/components/common/form-success";
import CardWrapper from "@/components/common/card-wrapper";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Info } from "lucide-react";
import forgotPassword from "../forgot-password";
import { getApiErrorMessage } from "@/lib/api-response";
import { cn } from "@/lib/utils";

const getFieldError = (error: unknown, field: string): string | undefined => {
  if (typeof error !== "object" || error === null) {
    return undefined;
  }

  const fieldValue = (error as Record<string, unknown>)[field];
  if (Array.isArray(fieldValue) && typeof fieldValue[0] === "string") {
    return fieldValue[0];
  }

  return undefined;
};



export default function ForgotPasswordForm() {

      
      const [error, setError] = useState<string | undefined>("");
      const [success, setSuccess] = useState("");
      const [isPending, startTransition] = useTransition();


      const form = useForm<z.infer<typeof ForgotPasswordSchema>>({
          resolver: zodResolver(ForgotPasswordSchema),
          defaultValues: {
              email: ""
          },
      });


      // 2. Define a submit handler.
      async function onSubmit(values: z.infer<typeof ForgotPasswordSchema>) {
        setError("");
        setSuccess("");
        startTransition(async () => {
          const data = await forgotPassword(values);
          if (data?.error) {
            if (typeof data.error === "object") {
              const emailError = getFieldError(data.error, "email");
              if (emailError) {
                form.setError("email", { type: "custom", message: emailError });
              }
            } else {
              setError(getApiErrorMessage(data.error, "Failed to send reset email"));
            }
            return;
          }

          form.reset();
          setSuccess(
            `Password reset link sent to ${values.email}. If you don't see it within a few minutes, check your spam or junk folder.`
          );
        });
      }

   
    return (
      <>
          <CardWrapper
            title="Forgot password"
            subtitle="We'll email you a link to reset your password."
            variant="auth"
          >
            <Alert className="mb-4 border-blue-200 bg-blue-50 dark:border-blue-900 dark:bg-blue-950/40">
              <Info className="h-4 w-4 text-blue-600" />
              <AlertDescription className="text-sm text-blue-900 dark:text-blue-100">
                The reset email may land in your <strong>spam or junk folder</strong>. If it
                doesn't arrive in your inbox, check there before requesting another link.
              </AlertDescription>
            </Alert>

            <Form {...form}>
            <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-4 sm:space-y-6">

                  <div className="mt-1">
                    <FormField
                          control={form.control}
                          name="email"
                          render={({ field }) => (
                              <FormItem>
                              <FormLabel>Email</FormLabel>
                              <FormControl>
                                  <Input disabled={isPending}  type="email" autoComplete="email" placeholder="email" {...field} />
                              </FormControl>
                              <FormMessage />
                              </FormItem>
                          )}
                          />
                    
                    </div>


                <FormError message={error} />

                <FormSuccess message={success} />

                <div>
                  <Button
                    type="submit"
                    disabled={isPending}
                    className="w-full text-white dark:text-gray-900 bg-teal-800 dark:bg-white"
                  >
                   Send
                  </Button>
                </div>
              </form>
              </Form>
  
          </CardWrapper>
          {/* <SignIn /> */}
      </>
    )
  }

  const LabelInputContainer = ({
    children,
    className,
  }: {
    children: React.ReactNode;
    className?: string;
  }) => {
    return (
      <div className={cn("flex flex-col space-y-2 w-full", className)}>
        {children}
      </div>
    );
  };
  
