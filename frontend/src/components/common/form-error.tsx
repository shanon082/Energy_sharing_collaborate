import { AlertTriangle } from 'lucide-react';
import { motion } from 'framer-motion';

interface FormErrorProps {
    message?: string;
}

export const FormError = ({ message }: FormErrorProps) => {
    if (!message) {
        return null;
    }

    return (
        <motion.div
            initial={{ opacity: 0, y: -10 }}
            animate={{ opacity: 1, y: 0 }}
            className="bg-gradient-to-r from-red-50/80 to-orange-50/80 dark:from-red-900/20 dark:to-orange-900/20 border-l-4 border-red-500 dark:border-red-400 p-4 rounded-lg shadow-sm"
        >
            <div className="flex items-center gap-3">
                <div className="flex-shrink-0">
                    <AlertTriangle className="h-5 w-5 text-red-500 dark:text-red-400" />
                </div>
                <div className="flex-1">
                    <p className="text-sm font-medium text-red-800 dark:text-red-200">
                        {message}
                    </p>
                </div>
            </div>
        </motion.div>
    );
}