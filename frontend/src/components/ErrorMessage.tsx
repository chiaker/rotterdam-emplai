import { AlertCircle } from 'lucide-react';

interface ErrorMessageProps {
  message: string;
  onRetry?: () => void;
}

export function ErrorMessage({ message, onRetry }: ErrorMessageProps) {
  return (
    <div className="p-4 bg-red-50 border border-red-200 rounded-lg">
      <div className="flex items-start">
        <AlertCircle className="w-5 h-5 text-red-500 mr-3 mt-0.5" />
        <div className="flex-1">
          <h3 className="text-sm font-medium text-red-800">Ошибка</h3>
          <p className="mt-1 text-sm text-red-600">{message}</p>
          {onRetry && (
            <button
              onClick={onRetry}
              className="mt-2 text-sm font-medium text-red-700 hover:text-red-800 underline"
            >
              Попробовать снова
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
