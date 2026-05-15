import { useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useQuery, useMutation } from '@tanstack/react-query';
import { getResume, deleteResume } from '../api/client';
import { SkillBadge } from '../components/SkillBadge';
import { LoadingSpinner } from '../components/LoadingSpinner';
import { ErrorMessage } from '../components/ErrorMessage';
import { ArrowLeft, MapPin, Clock, FileText, User, Trash2, ChevronDown, ChevronUp } from 'lucide-react';

export function ResumeDetail() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const [showRawText, setShowRawText] = useState(false);

  const { data: resume, isLoading, error, refetch } = useQuery({
    queryKey: ['resume', id],
    queryFn: () => getResume(Number(id)),
    enabled: !!id,
  });

  const deleteMutation = useMutation({
    mutationFn: deleteResume,
    onSuccess: () => {
      navigate('/resumes');
    },
  });

  const handleDelete = () => {
    if (window.confirm('Вы уверены, что хотите удалить это резюме?')) {
      deleteMutation.mutate(Number(id));
    }
  };

  if (isLoading) return <LoadingSpinner />;
  if (error) return <ErrorMessage message="Ошибка загрузки резюме" onRetry={() => refetch()} />;
  if (!resume) return <ErrorMessage message="Резюме не найдено" />;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <button
          onClick={() => navigate('/resumes')}
          className="flex items-center text-gray-600 hover:text-gray-900"
        >
          <ArrowLeft className="w-5 h-5 mr-2" />
          Назад к списку
        </button>
        <button
          onClick={handleDelete}
          className="flex items-center px-4 py-2 text-red-600 hover:bg-red-50 rounded-lg transition-colors"
          disabled={deleteMutation.isPending}
        >
          <Trash2 className="w-5 h-5 mr-2" />
          Удалить
        </button>
      </div>

      {/* Main Info */}
      <div className="bg-white rounded-lg shadow p-6">
        <div className="flex items-start justify-between">
          <div>
            <div className="flex items-center">
              <User className="w-8 h-8 text-primary-600 mr-3" />
              <h1 className="text-2xl font-bold text-gray-900">
                {resume.candidate_name || 'Кандидат #' + resume.id}
              </h1>
            </div>
            <p className="mt-2 text-sm text-gray-500 uppercase">{resume.source_format}</p>
          </div>
        </div>

        <div className="mt-6 grid gap-4 md:grid-cols-2">
          {resume.location && (
            <div className="flex items-center">
              <MapPin className="w-5 h-5 text-gray-400 mr-2" />
              <span className="text-gray-700">{resume.location}</span>
            </div>
          )}
          {resume.preferred_work_format && (
            <div className="flex items-center">
              <Clock className="w-5 h-5 text-gray-400 mr-2" />
              <span className="text-gray-700">{resume.preferred_work_format}</span>
            </div>
          )}
        </div>
      </div>

      {/* Skills */}
      <div className="bg-white rounded-lg shadow p-6">
        <h2 className="text-lg font-medium text-gray-900 mb-4">Навыки</h2>
        
        <div className="mb-6">
          <h3 className="text-sm font-medium text-blue-700 mb-3">Хард-скиллы:</h3>
          <div className="flex flex-wrap gap-2">
            {resume.hard_skills.length > 0 ? (
              resume.hard_skills.map((skill, idx) => (
                <SkillBadge key={idx} skill={skill} type="hard" />
              ))
            ) : (
              <p className="text-sm text-gray-500">Не указаны</p>
            )}
          </div>
        </div>

        <div>
          <h3 className="text-sm font-medium text-green-700 mb-3">Софт-скиллы:</h3>
          <div className="flex flex-wrap gap-2">
            {resume.soft_skills.length > 0 ? (
              resume.soft_skills.map((skill, idx) => (
                <SkillBadge key={idx} skill={skill} type="soft" />
              ))
            ) : (
              <p className="text-sm text-gray-500">Не указаны</p>
            )}
          </div>
        </div>
      </div>

      {/* Experience */}
      {resume.experience && Object.keys(resume.experience).length > 0 && (
        <div className="bg-white rounded-lg shadow p-6">
          <h2 className="text-lg font-medium text-gray-900 mb-4">Опыт работы</h2>
          <div className="space-y-2">
            {resume.experience.total_years !== undefined && (
              <p className="text-gray-700">
                Общий опыт: {resume.experience.total_years} лет
              </p>
            )}
            {resume.experience.positions && resume.experience.positions.length > 0 && (
              <p className="text-gray-700">
                Позиции: {resume.experience.positions.join(', ')}
              </p>
            )}
          </div>
        </div>
      )}

      {/* Raw Text */}
      <div className="bg-white rounded-lg shadow">
        <button
          onClick={() => setShowRawText(!showRawText)}
          className="w-full p-4 flex items-center justify-between text-left hover:bg-gray-50"
        >
          <span className="font-medium text-gray-900">Исходный текст</span>
          {showRawText ? (
            <ChevronUp className="w-5 h-5 text-gray-400" />
          ) : (
            <ChevronDown className="w-5 h-5 text-gray-400" />
          )}
        </button>
        {showRawText && (
          <div className="p-4 pt-0 border-t">
            <pre className="whitespace-pre-wrap text-sm text-gray-700 font-mono">
              {resume.raw_text}
            </pre>
          </div>
        )}
      </div>
    </div>
  );
}
