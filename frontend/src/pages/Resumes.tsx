import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { getResumes, uploadResume, deleteResume } from '../api/client';
import { UploadDropzone } from '../components/UploadDropzone';
import { LoadingSpinner } from '../components/LoadingSpinner';
import { ErrorMessage } from '../components/ErrorMessage';
import { FileText, MapPin, User, Trash2 } from 'lucide-react';

export function Resumes() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [uploadError, setUploadError] = useState<string | null>(null);

  const { data: resumes, isLoading, error, refetch } = useQuery({
    queryKey: ['resumes'],
    queryFn: getResumes,
  });

  const deleteMutation = useMutation({
    mutationFn: deleteResume,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['resumes'] });
    },
  });

  const uploadMutation = useMutation({
    mutationFn: uploadResume,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['resumes'] });
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
    if (window.confirm('Вы уверены, что хотите удалить это резюме?')) {
      deleteMutation.mutate(id);
    }
  };

  if (isLoading) return <LoadingSpinner />;
  if (error) return <ErrorMessage message="Ошибка загрузки резюме" onRetry={() => refetch()} />;

  return (
    <div className="space-y-6">
      <div className="flex justify-between items-center">
        <h1 className="text-2xl font-bold text-gray-900">Резюме</h1>
        <span className="text-sm text-gray-500">{resumes?.length || 0} резюме</span>
      </div>

      {/* Upload Section */}
      <div className="bg-white rounded-lg shadow p-6">
        <h2 className="text-lg font-medium text-gray-900 mb-4">Загрузить резюме</h2>
        <UploadDropzone onUpload={handleUpload} label="Перетащите файл резюме сюда" />
        {uploadError && (
          <div className="mt-4">
            <ErrorMessage message={uploadError} />
          </div>
        )}
      </div>

      {/* Resumes List */}
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
        {resumes?.map((resume) => (
          <div
            key={resume.id}
            className="bg-white rounded-lg shadow p-6 hover:shadow-md transition-shadow cursor-pointer"
            onClick={() => navigate(`/resumes/${resume.id}`)}
          >
            <div className="flex justify-between items-start">
              <div className="flex-1">
                <div className="flex items-center">
                  <FileText className="w-5 h-5 text-primary-600 mr-2" />
                  <h3 className="text-lg font-medium text-gray-900">
                    {resume.candidate_name || 'Кандидат #' + resume.id}
                  </h3>
                </div>
                <p className="mt-1 text-sm text-gray-500 uppercase">{resume.source_format}</p>
              </div>
              <button
                onClick={(e) => {
                  e.stopPropagation();
                  handleDelete(resume.id);
                }}
                className="p-2 text-gray-400 hover:text-red-500 transition-colors"
                disabled={deleteMutation.isPending}
              >
                <Trash2 className="w-5 h-5" />
              </button>
            </div>

            <div className="mt-4 space-y-2">
              {resume.location && (
                <div className="flex items-center text-sm text-gray-600">
                  <MapPin className="w-4 h-4 mr-1" />
                  {resume.location}
                </div>
              )}
              {resume.preferred_work_format && (
                <div className="inline-block px-2 py-1 text-xs font-medium bg-gray-100 text-gray-700 rounded">
                  {resume.preferred_work_format}
                </div>
              )}
              <p className="text-xs text-gray-400">
                {new Date(resume.created_at).toLocaleDateString('ru-RU')}
              </p>
            </div>
          </div>
        ))}
      </div>

      {resumes?.length === 0 && (
        <div className="text-center py-12">
          <FileText className="w-12 h-12 text-gray-300 mx-auto mb-4" />
          <p className="text-gray-500">Нет загруженных резюме</p>
          <p className="text-sm text-gray-400 mt-1">Загрузите файл выше, чтобы начать</p>
        </div>
      )}
    </div>
  );
}
