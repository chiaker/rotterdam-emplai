import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { 
  getVacancies, 
  getResumes, 
  getMatchesForVacancy, 
  getMatchesForResume,
  getOrphanVacancies,
  getOrphanResumes 
} from '../api/client';
import { MatchCard } from '../components/MatchCard';
import { LoadingSpinner } from '../components/LoadingSpinner';
import { ErrorMessage } from '../components/ErrorMessage';
import { Briefcase, FileText, Users } from 'lucide-react';

type TabType = 'top-vacancy' | 'top-resume' | 'orphan-vacancies' | 'orphan-resumes';

export function Matches() {
  const [activeTab, setActiveTab] = useState<TabType>('top-vacancy');
  const [selectedVacancyId, setSelectedVacancyId] = useState<number | null>(null);
  const [selectedResumeId, setSelectedResumeId] = useState<number | null>(null);
  const [topCount, setTopCount] = useState(10);

  const { data: vacancies } = useQuery({
    queryKey: ['vacancies'],
    queryFn: getVacancies,
  });

  const { data: resumes } = useQuery({
    queryKey: ['resumes'],
    queryFn: getResumes,
  });

  const { data: vacancyMatches, isLoading: vacancyMatchesLoading } = useQuery({
    queryKey: ['matches', 'vacancy', selectedVacancyId, topCount],
    queryFn: () => getMatchesForVacancy(selectedVacancyId!, topCount),
    enabled: !!selectedVacancyId,
  });

  const { data: resumeMatches, isLoading: resumeMatchesLoading } = useQuery({
    queryKey: ['matches', 'resume', selectedResumeId, topCount],
    queryFn: () => getMatchesForResume(selectedResumeId!, topCount),
    enabled: !!selectedResumeId,
  });

  const { data: orphanVacancies, isLoading: orphanVacanciesLoading } = useQuery({
    queryKey: ['matches', 'orphan-vacancies', topCount],
    queryFn: () => getOrphanVacancies(topCount),
    enabled: activeTab === 'orphan-vacancies',
  });

  const { data: orphanResumes, isLoading: orphanResumesLoading } = useQuery({
    queryKey: ['matches', 'orphan-resumes', topCount],
    queryFn: () => getOrphanResumes(topCount),
    enabled: activeTab === 'orphan-resumes',
  });

  const tabs = [
    { id: 'top-vacancy' as TabType, label: 'Топ-N кандидатов для вакансии' },
    { id: 'top-resume' as TabType, label: 'Топ-K вакансий для кандидата' },
    { id: 'orphan-vacancies' as TabType, label: 'Вакансии без мэтчей' },
    { id: 'orphan-resumes' as TabType, label: 'Кандидаты без мэтчей' },
  ];

  const renderContent = () => {
    switch (activeTab) {
      case 'top-vacancy':
        return (
          <div className="space-y-6">
            <div className="bg-white rounded-lg shadow p-6">
              <h2 className="text-lg font-medium text-gray-900 mb-4">Выберите вакансию</h2>
              <div className="grid gap-4 md:grid-cols-2">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">Вакансия</label>
                  <select
                    value={selectedVacancyId || ''}
                    onChange={(e) => setSelectedVacancyId(Number(e.target.value) || null)}
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-primary-500 focus:border-primary-500"
                  >
                    <option value="">Выберите вакансию...</option>
                    {vacancies?.map((v) => (
                      <option key={v.id} value={v.id}>{v.title}</option>
                    ))}
                  </select>
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">Количество результатов</label>
                  <select
                    value={topCount}
                    onChange={(e) => setTopCount(Number(e.target.value))}
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-primary-500 focus:border-primary-500"
                  >
                    <option value={5}>5</option>
                    <option value={10}>10</option>
                    <option value={20}>20</option>
                    <option value={50}>50</option>
                  </select>
                </div>
              </div>
            </div>

            {vacancyMatchesLoading && <LoadingSpinner />}

            {selectedVacancyId && !vacancyMatchesLoading && (
              <div>
                <h3 className="text-lg font-medium text-gray-900 mb-4">
                  Найдено кандидатов: {vacancyMatches?.length || 0}
                </h3>
                {vacancyMatches && vacancyMatches.length > 0 ? (
                  <div className="grid gap-4 md:grid-cols-2">
                    {vacancyMatches.map((match) => (
                      <MatchCard key={match.id} match={match} showCandidate />
                    ))}
                  </div>
                ) : (
                  <div className="text-center py-12 bg-white rounded-lg shadow">
                    <Users className="w-12 h-12 text-gray-300 mx-auto mb-4" />
                    <p className="text-gray-500">Кандидаты не найдены</p>
                  </div>
                )}
              </div>
            )}
          </div>
        );

      case 'top-resume':
        return (
          <div className="space-y-6">
            <div className="bg-white rounded-lg shadow p-6">
              <h2 className="text-lg font-medium text-gray-900 mb-4">Выберите кандидата</h2>
              <div className="grid gap-4 md:grid-cols-2">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">Кандидат</label>
                  <select
                    value={selectedResumeId || ''}
                    onChange={(e) => setSelectedResumeId(Number(e.target.value) || null)}
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-primary-500 focus:border-primary-500"
                  >
                    <option value="">Выберите резюме...</option>
                    {resumes?.map((r) => (
                      <option key={r.id} value={r.id}>
                        {r.candidate_name || 'Кандидат #' + r.id}
                      </option>
                    ))}
                  </select>
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">Количество результатов</label>
                  <select
                    value={topCount}
                    onChange={(e) => setTopCount(Number(e.target.value))}
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-primary-500 focus:border-primary-500"
                  >
                    <option value={5}>5</option>
                    <option value={10}>10</option>
                    <option value={20}>20</option>
                    <option value={50}>50</option>
                  </select>
                </div>
              </div>
            </div>

            {resumeMatchesLoading && <LoadingSpinner />}

            {selectedResumeId && !resumeMatchesLoading && (
              <div>
                <h3 className="text-lg font-medium text-gray-900 mb-4">
                  Найдено вакансий: {resumeMatches?.length || 0}
                </h3>
                {resumeMatches && resumeMatches.length > 0 ? (
                  <div className="grid gap-4 md:grid-cols-2">
                    {resumeMatches.map((match) => (
                      <MatchCard key={match.id} match={match} showVacancy />
                    ))}
                  </div>
                ) : (
                  <div className="text-center py-12 bg-white rounded-lg shadow">
                    <Briefcase className="w-12 h-12 text-gray-300 mx-auto mb-4" />
                    <p className="text-gray-500">Вакансии не найдены</p>
                  </div>
                )}
              </div>
            )}
          </div>
        );

      case 'orphan-vacancies':
        return (
          <div className="space-y-6">
            <div className="bg-white rounded-lg shadow p-6">
              <h2 className="text-lg font-medium text-gray-900 mb-4">
                Вакансии без подходящих кандидатов ( score {'<'} 85%)
              </h2>
              <div className="grid gap-4 md:grid-cols-3">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">Количество результатов</label>
                  <select
                    value={topCount}
                    onChange={(e) => setTopCount(Number(e.target.value))}
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-primary-500 focus:border-primary-500"
                  >
                    <option value={5}>5</option>
                    <option value={10}>10</option>
                    <option value={20}>20</option>
                  </select>
                </div>
              </div>
            </div>

            {orphanVacanciesLoading && <LoadingSpinner />}

            {!orphanVacanciesLoading && (
              <div>
                <h3 className="text-lg font-medium text-gray-900 mb-4">
                  Найдено вакансий: {orphanVacancies?.length || 0}
                </h3>
                {orphanVacancies && orphanVacancies.length > 0 ? (
                  <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
                    {orphanVacancies.map((vacancy) => (
                      <div key={vacancy.id} className="bg-white rounded-lg shadow p-4">
                        <div className="flex items-center">
                          <Briefcase className="w-5 h-5 text-primary-600 mr-2" />
                          <span className="font-medium text-gray-900">{vacancy.title}</span>
                        </div>
                        <p className="mt-2 text-sm text-gray-500">{vacancy.location}</p>
                      </div>
                    ))}
                  </div>
                ) : (
                  <div className="text-center py-12 bg-white rounded-lg shadow">
                    <Briefcase className="w-12 h-12 text-gray-300 mx-auto mb-4" />
                    <p className="text-gray-500">Все вакансии имеют подходящих кандидатов</p>
                  </div>
                )}
              </div>
            )}
          </div>
        );

      case 'orphan-resumes':
        return (
          <div className="space-y-6">
            <div className="bg-white rounded-lg shadow p-6">
              <h2 className="text-lg font-medium text-gray-900 mb-4">
                Кандидаты без подходящих вакансий ( score {'<'} 85%)
              </h2>
              <div className="grid gap-4 md:grid-cols-3">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">Количество результатов</label>
                  <select
                    value={topCount}
                    onChange={(e) => setTopCount(Number(e.target.value))}
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-primary-500 focus:border-primary-500"
                  >
                    <option value={5}>5</option>
                    <option value={10}>10</option>
                    <option value={20}>20</option>
                  </select>
                </div>
              </div>
            </div>

            {orphanResumesLoading && <LoadingSpinner />}

            {!orphanResumesLoading && (
              <div>
                <h3 className="text-lg font-medium text-gray-900 mb-4">
                  Найдено кандидатов: {orphanResumes?.length || 0}
                </h3>
                {orphanResumes && orphanResumes.length > 0 ? (
                  <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
                    {orphanResumes.map((resume) => (
                      <div key={resume.id} className="bg-white rounded-lg shadow p-4">
                        <div className="flex items-center">
                          <FileText className="w-5 h-5 text-primary-600 mr-2" />
                          <span className="font-medium text-gray-900">
                            {resume.candidate_name || 'Кандидат #' + resume.id}
                          </span>
                        </div>
                        <p className="mt-2 text-sm text-gray-500">{resume.location}</p>
                      </div>
                    ))}
                  </div>
                ) : (
                  <div className="text-center py-12 bg-white rounded-lg shadow">
                    <FileText className="w-12 h-12 text-gray-300 mx-auto mb-4" />
                    <p className="text-gray-500">Все кандидаты имеют подходящие вакансии</p>
                  </div>
                )}
              </div>
            )}
          </div>
        );
    }
  };

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold text-gray-900">Мэтчи</h1>

      {/* Tabs */}
      <div className="border-b border-gray-200">
        <nav className="flex space-x-8">
          {tabs.map((tab) => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={`
                pb-4 px-1 border-b-2 font-medium text-sm transition-colors
                ${activeTab === tab.id
                  ? 'border-primary-500 text-primary-600'
                  : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
                }
              `}
            >
              {tab.label}
            </button>
          ))}
        </nav>
      </div>

      {renderContent()}
    </div>
  );
}
