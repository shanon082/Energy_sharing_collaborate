export default function VerifyPendingPage() {
  return (
    <div className="flex flex-col items-center justify-center h-screen">
      <h1 className="text-xl font-bold">Verify your email</h1>
      <p className="mt-2 text-gray-600">
        We have sent a verification link to your email address. 
        Please check your inbox (and spam folder) to activate your account.
      </p>
      <p className="mt-4 text-sm text-gray-500">
        Didn’t get the email? <a href="/auth/resend-verification" className="text-blue-500">Resend</a>
      </p>
    </div>
  )
}
