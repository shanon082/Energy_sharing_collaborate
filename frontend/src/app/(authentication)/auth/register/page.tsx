import { Suspense } from 'react'
import RegisterForm from './_components/form';
import Link from 'next/link';
import { ChevronRight } from 'lucide-react';



const RegistrationPage = async ({params}: {params: any}) => {


    return (
      <div className="min-h-[calc(100dvh-4rem)] bg-gradient-to-br from-blue-50 via-emerald-50 to-blue-100 dark:from-blue-950 dark:via-emerald-900/20 dark:to-blue-900">
         <Suspense fallback={<div>Server error</div>}>
            <RegisterForm />

            {/* <div className="sm:mx-auto sm:w-full sm:max-w-md flex justify-center items-center">
                <Link className="text-white inline-flex" href="/auth/login"><span>Login</span> <ChevronRight /></Link>
            </div> */}

        </Suspense>
      </div>
    );
}

export default RegistrationPage;
