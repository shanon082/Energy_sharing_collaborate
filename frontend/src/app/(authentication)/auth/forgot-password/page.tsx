import {get} from "@/lib/fetch"
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import ForgotPasswordForm from "./_components/form";

const ForgotPasswordPage = async () => {
    
    // const response = await get<{status_code?: number, error?: string, message?: string}>('auth/forgot-password/');
    return (
      <div className="min-h-screen overflow-hidden bg-gradient-to-br from-blue-50 via-emerald-50 to-blue-100 dark:from-blue-950 dark:via-emerald-900/20 dark:to-blue-900">
        <div>
        {/* {response?.data?.message && <><Alert>
            {
            <AlertTitle>Success!</AlertTitle>
            <AlertDescription>
                {response?.data?.message}
            </AlertDescription>
        </Alert>
        <ForgotPasswordForm />
        </>} */}
        <ForgotPasswordForm />
        {/* {response?.error && <Alert variant={"destructive"}>
            
            <AlertTitle>Error!</AlertTitle>
            <AlertDescription>
                {response?.error?.message}
            </AlertDescription>
        </Alert>} */}
        </div>
      </div>
    );
}

export default ForgotPasswordPage;
