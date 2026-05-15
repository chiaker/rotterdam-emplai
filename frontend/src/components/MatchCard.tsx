import { useState } from 'react';
import { ChevronDown, ChevronUp, User, Briefcase } from 'lucide-react';
import type { Match } from '../types/api';

interface MatchCardProps {
  match: Match;
  showVacancy?: boolean;
  showCandidate?: boolean;
}

export function MatchCard({ match, showVacancy = true, showCandidate = true }: MatchCardProps) {
  const [isExpanded, setIsExpanded] = useState(false);

  const getScoreColor = (score: number) => {
    if (score >= 85) return 'bg-green-500';
    if (score >= 70) return 'bg-yellow-500';
    return 'bg-red-500';
  };

  return (
    <div className="bg-white rounded-lg shadow-md p-6">
      {/* Header */}
      <div className="flex justify-between items-start mb-4">
        <div className="flex-1">
          {showCandidate && match.candidate_name && (
            <div className="flex items-center text-gray-700 mb-2">
              <User className="w-4 h-4 mr-2" />
              <span className="font-medium">{match.candidate_name}</span>
            </div>
          )}
          {showVacancy && match.vacancy_title && (
            <div className="flex items-center text-gray-700 mb-2">
              <Briefcase className="w-4 h-4 mr-2" />
              <span className="font-medium">{match.vacancy_title}</span>
            </div>
          )}
        </div>
        
        {/* Score Badge */}
        <div className="flex flex-col items-end">
          <span className="text-2xl font-bold text-gray-900">{match.score}%</span>
          <span className="text-xs text-gray-500">
            {new Date(match.computed_at).toLocaleDateString('ru-RU')}
          </span>
        </div>
      </div>

      {/* Progress Bar */}
      <div className="mb-4">
        <div className="h-2 bg-gray-200 rounded-full overflow-hidden">
          <div
            className={`h-full ${getScoreColor(match.score)} transition-all duration-500`}
            style={{ width: `${match.score}%` }}
          />
        </div>
      </div>

      {/* Skills Summary */}
      <div className="grid grid-cols-2 gap-4 mb-4">
        <div>
          <h4 className="text-sm font-medium text-green-700 mb-2">Совпадения:</h4>
          <div className="flex flex-wrap gap-1">
            {match.matching_skills.slice(0, 5).map((skill, idx) => (
              <span
                key={idx}
                className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium bg-green-100 text-green-800"
              >
                {skill}
              </span>
            ))}
            {match.matching_skills.length > 5 && (
              <span className="text-xs text-gray-500">+{match.matching_skills.length - 5}</span>
            )}
          </div>
        </div>
        <div>
          <h4 className="text-sm font-medium text-red-700 mb-2">Отсутствуют:</h4>
          <div className="flex flex-wrap gap-1">
            {match.missing_skills.slice(0, 5).map((skill, idx) => (
              <span
                key={idx}
                className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium bg-red-100 text-red-800"
              >
                {skill}
              </span>
            ))}
            {match.missing_skills.length > 5 && (
              <span className="text-xs text-gray-500">+{match.missing_skills.length - 5}</span>
            )}
          </div>
        </div>
      </div>

      {/* Expandable Explanation */}
      <button
        onClick={() => setIsExpanded(!isExpanded)}
        className="flex items-center text-sm text-primary-600 hover:text-primary-700"
      >
        {isExpanded ? (
          <>
            <ChevronUp className="w-4 h-4 mr-1" />
            Скрыть обоснование
          </>
        ) : (
          <>
            <ChevronDown className="w-4 h-4 mr-1" />
            Показать обоснование
          </>
        )}
      </button>

      {isExpanded && (
        <div className="mt-4 p-4 bg-gray-50 rounded-lg">
          <p className="text-sm text-gray-700 whitespace-pre-wrap">{match.explanation}</p>
        </div>
      )}
    </div>
  );
}
