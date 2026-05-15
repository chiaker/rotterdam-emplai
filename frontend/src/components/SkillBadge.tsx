import type { Skill } from '../types/api';

interface SkillBadgeProps {
  skill: Skill;
  type: 'hard' | 'soft';
  size?: 'sm' | 'md' | 'lg';
}

export function SkillBadge({ skill, type, size = 'md' }: SkillBadgeProps) {
  const sizeClasses = {
    sm: 'text-xs px-2 py-0.5',
    md: 'text-sm px-2.5 py-1',
    lg: 'text-base px-3 py-1.5',
  };

  const typeStyles = {
    hard: 'bg-blue-100 text-blue-800 border-blue-200',
    soft: 'bg-green-100 text-green-800 border-green-200',
  };

  return (
    <span
      className={`inline-flex items-center rounded-full border font-medium ${sizeClasses[size]} ${typeStyles[type]}`}
    >
      {skill.name}
      {skill.level && (
        <span className="ml-1 opacity-75">({skill.level})</span>
      )}
    </span>
  );
}
