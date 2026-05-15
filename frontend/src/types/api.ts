// Auth types
export interface RegisterRequest {
  email: string;
  password: string;
}

export interface TokenResponse {
  access_token: string;
  token_type: string;
  expires_in: number;
}

export interface UserResponse {
  id: number;
  email: string;
  created_at: string;
}

// Skill types
export interface Skill {
  name: string;
  level?: string;
  required?: boolean;
}

export interface Experience {
  years_min?: number;
  years_max?: number;
  domains?: string[];
  total_years?: number;
  positions?: string[];
}

// Vacancy types
export interface VacancyListItem {
  id: number;
  title: string;
  source_format: string;
  location: string | null;
  work_format: string | null;
  created_at: string;
}

export interface VacancyResponse {
  id: number;
  owner_id: number;
  title: string;
  raw_text: string;
  source_format: string;
  hard_skills: Skill[];
  soft_skills: Skill[];
  experience: Experience;
  location: string | null;
  work_format: string | null;
  work_hours: string | null;
  other_requirements: Record<string, unknown>;
  created_at: string;
}

// Resume types
export interface ResumeListItem {
  id: number;
  candidate_name: string | null;
  source_format: string;
  location: string | null;
  preferred_work_format: string | null;
  created_at: string;
}

export interface ResumeResponse {
  id: number;
  owner_id: number;
  candidate_name: string | null;
  raw_text: string;
  source_format: string;
  hard_skills: Skill[];
  soft_skills: Skill[];
  experience: Experience;
  location: string | null;
  preferred_work_format: string | null;
  other_traits: Record<string, unknown>;
  created_at: string;
}

// Match types
export interface Match {
  id: number;
  vacancy_id: number;
  resume_id: number;
  score: number;
  explanation: string;
  missing_skills: string[];
  matching_skills: string[];
  computed_at: string;
  candidate_name?: string;
  vacancy_title?: string;
}

// API Error type
export interface ApiError {
  detail: string;
}
