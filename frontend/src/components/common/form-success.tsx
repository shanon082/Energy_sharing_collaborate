import { CheckCircle } from 'lucide-react';
import { motion } from 'framer-motion';

interface FormSuccessProps {
    message?: string;
}

export const FormSuccess = ({ message }: FormSuccessProps) => {
    if (!message) {
        return null;
    }

    return (
        <motion.div
            initial={{ opacity: 0, y: -10 }}
            animate={{ opacity: 1, y: 0 }}
            className="bg-gradient-to-r from-emerald-50/80 to-blue-50/80 dark:from-emerald-900/20 dark:to-blue-900/20 border-l-4 border-emerald-500 dark:border-emerald-400 p-4 rounded-lg shadow-sm"
        >
            <div className="flex items-center gap-3">
                <div className="flex-shrink-0">
                    <CheckCircle className="h-5 w-5 text-emerald-500 dark:text-emerald-400" />
                </div>
                <div className="flex-1">
                    <p className="text-sm font-medium text-emerald-800 dark:text-emerald-200">
                        {message}
                    </p>
                </div>
            </div>
        </motion.div>
    );
}