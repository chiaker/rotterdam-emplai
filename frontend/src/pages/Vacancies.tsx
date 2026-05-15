import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { getVacancies, uploadVacancy, deleteVacancy } from '../api/client';
import { UploadDropzone } from '../components/UploadDropzone';
import { LoadingSpinner } from '../components/LoadingSpinner';
import { ErrorMessage } from '../components/ErrorMessage';
import { Briefcase, MapPin, Trash2 } from 'lucide-react';

export function Vacancies() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [uploadError, setUploadError] = useState<string | null>(null);

  const { data: vacancies, isLoading, error, refetch } = useQuery({
    queryKey: ['vacancies'],
    queryFn: getVacancies,
  });

  const deleteMutation = useMutation({
    mutationFn: deleteVacancy,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['vacancies'] });
    },
  });

  const uploadMutation = useMutation({
    mutationFn: uploadVacancy,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['vacancies'] });
      setUploadError(null);
    },
    onError: (err: unknown) => {
      if (err && typeof err === 'object' && 'response' in err) {
        const axiosError = err as { response?: { data?: { detail?: string } } };
        setUploadError(axiosError.response?.data?.detail || 'Ошибка загрузки');
      } else {
        setUploadError('Ошибка загрузки файла');
      }
    },
  });

  const handleUpload = async (file: File) => {
    await uploadMutation.mutateAsync(file);
  };

  const handleDelete = (id: number) => {
    if (window.confirm('Вы уверены, что хотите удалить эту вакансию?')) {
      deleteMutation.mutate(id);
    }
  };

  if (isLoading) return <LoadingSpinner />;
  if (error) return <ErrorMessage message="Ошибка загрузки вакансий" onRetry={() => refetch()} />;

  return (
    <div className="space-y-6">
      <div className="flex justify-between items-center">
        <h1 className="text-2xl font-bold text-gray-900">Вакансии</h1>
        <span className="text-sm text-gray-500">{vacancies?.length || 0} вакансий</span>
      </div>

      {/* Upload Section */}
      <div className="bg-white rounded-lg shadow p-6">
        <h2 className="text-lg font-medium text-gray-900 mb-4">Загрузить вакансию</h2>
        <UploadDropzone onUpload={handleUpload} label="Перетащите файл вакансии сюда" />
        {uploadError && (
          <div className="mt-4">
            <ErrorMessage message={uploadError} />
          </div>
        )}
      </div>

      {/* Vacancies List */}
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
        {vacancies?.map((vacancy) => (
          <div
            key={vacancy.id}
            className="bg-white rounded-lg shadow p-6 hover:shadow-md transition-shadow cursor-pointer"
            onClick={() => navigate(`/vacancies/${vacancy.id}`)}
          >
            <div className="flex justify-between items-start">
              <div className="flex-1">
                <div className="flex items-center">
                  <Briefcase className="w-5 h-5 text-primary-600 mr-2" />
                  <h3 className="text-lg font-medium text-gray-900">{vacancy.title}</h3>
                </div>
                <p className="mt-1 text-sm text-gray-500 uppercase">{vacancy.source_format}</p>
              </div>
              <button
                onClick={(e) => {
                  e.stopPropagation();
                  handleDelete(vacancy.id);
                }}
                className="p-2 text-gray-400 hover:text-red-500 transition-colors"
                disabled={deleteMutation.isPending}
              >
                <Trash2 className="w-5 h-5" />
              </button>
            </div>

            <div className="mt-4 space-y-2">
              {vacancy.location && (
                <div className="flex items-center text-sm text-gray-600">
                  <MapPin className="w-4 h-4 mr-1" />
                  {vacancy.location}
                </div>
              )}
              {vacancy.work_format && (
                <div className="inline-block px-2 py-1 text-xs font-medium bg-gray-100 text-gray-700 rounded">
                  {vacancy.work_format}
                </div>
              )}
              <p className="text-xs text-gray-400">
                {new Date(vacancy.created_at).toLocaleDateString('ru-RU')}
              </p>
            </div>
          </div>
        ))}
      </div>

      {vacancies?.length === 0 && (
        <div className="text-center py-12">
          <Briefcase className="w-12 h-12 text-gray-300 mx-auto mb-4" />
          <p className="text-gray-500">Нет загруженных вакансий</p>
          <p className="text-sm text-gray-400 mt-1">Загрузите файл выше, чтобы начать</p>
        </div>
      )}
    </div>
  );
}
