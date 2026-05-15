import { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import { login } from '../api/client';
import { useAuthStore } from '../store/auth';

const loginSchema = z.object({
  email: z.string().email('Неверный формат email'),
  password: z.string().min(1, 'Введите пароль'),
});

type LoginForm = z.infer<typeof loginSchema>;

export function Login() {
  const [error, setError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const navigate = useNavigate();
  const { setToken, setDemoMode } = useAuthStore();

  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<LoginForm>({
    resolver: zodResolver(loginSchema),
  });

  const onSubmit = async (data: LoginForm) => {
    setIsLoading(true);
    setError(null);

    try {
      const response = await login(data.email, data.password);
      setToken(response.access_token);
      navigate('/vacancies');
    } catch (err: unknown) {
      if (err && typeof err === 'object' && 'response' in err) {
        const axiosError = err as { response?: { data?: { detail?: string } } };
        setError(axiosError.response?.data?.detail || 'Ошибка входа');
      } else {
        setError('Ошибка входа');
      }
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-100">
      <div className="max-w-md w-full space-y-8 p-8 bg-white rounded-xl shadow-lg">
        <div className="text-center">
          <h1 className="text-3xl font-bold text-primary-600">EmplAI</h1>
          <h2 className="mt-6 text-2xl font-bold text-gray-900">Вход в систему</h2>
          <p className="mt-2 text-sm text-gray-600">
            AI-ассистент рекрутера
          </p>
        </div>

        <form className="mt-8 space-y-6" onSubmit={handleSubmit(onSubmit)}>
          {error && (
            <div className="p-4 bg-red-50 border border-red-200 rounded-lg">
              <p className="text-sm text-red-600">{error}</p>
            </div>
          )}

          <div className="space-y-4">
            <div>
              <label htmlFor="email" className="block text-sm font-medium text-gray-700">
                Email
              </label>
              <input
                {...register('email')}
                type="email"
                id="email"
                className="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-lg shadow-sm focus:outline-none focus:ring-primary-500 focus:border-primary-500"
                placeholder="your@email.com"
              />
              {errors.email && (
                <p className="mt-1 text-sm text-red-600">{errors.email.message}</p>
              )}
            </div>

            <div>
              <label htmlFor="password" className="block text-sm font-medium text-gray-700">
                Пароль
              </label>
              <input
                {...register('password')}
                type="password"
                id="password"
                className="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-lg shadow-sm focus:outline-none focus:ring-primary-500 focus:border-primary-500"
                placeholder="••••••••"
              />
              {errors.password && (
                <p className="mt-1 text-sm text-red-600">{errors.password.message}</p>
              )}
            </div>
          </div>

          <button
            type="submit"
            disabled={isLoading}
            className="w-full flex justify-center py-2 px-4 border border-transparent rounded-lg shadow-sm text-sm font-medium text-white bg-primary-600 hover:bg-primary-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-primary-500 disabled:bg-gray-400"
          >
            {isLoading ? 'Вход...' : 'Войти'}
          </button>

          <div className="text-center">
            <p className="text-sm text-gray-600">
              Нет аккаунта?{' '}
              <Link to="/register" className="font-medium text-primary-600 hover:text-primary-500">
                Зарегистрироваться
              </Link>
            </p>
          </div>
          
          <div className="border-t border-gray-200 pt-4 mt-4">
            <button
              type="button"
              onClick={() => {
                setDemoMode();
                navigate('/vacancies');
              }}
              className="w-full flex justify-center py-2 px-4 border border-gray-300 rounded-lg shadow-sm text-sm font-medium text-gray-700 bg-gray-50 hover:bg-gray-100 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-primary-500"
            >
              Войти как гость
            </button>
            <p className="text-xs text-gray-500 text-center mt-2">
              Демо-режим без регистрации
            </p>
          </div>
        </form>
      </div>
    </div>
  );
}
