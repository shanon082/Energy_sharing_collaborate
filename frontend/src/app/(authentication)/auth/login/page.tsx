import { Suspense } from 'react'
import LoginForm from "./_components/form"
const LoginPage = async () => {
    return (
      <div className="min-h-[calc(100dvh-4rem)] bg-gradient-to-br from-blue-50 via-emerald-50 to-blue-100 dark:from-blue-950 dark:via-emerald-900/20 dark:to-blue-900">
        <Suspense>
            <LoginForm />
        </Suspense>
      </div>
    );
}

export default LoginPage;
