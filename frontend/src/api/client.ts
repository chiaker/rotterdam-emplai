import axios, { AxiosInstance, AxiosError } from 'axios';
import type {
  RegisterRequest,
  TokenResponse,
  UserResponse,
  VacancyListItem,
  VacancyResponse,
  ResumeListItem,
  ResumeResponse,
  Match,
} from '../types/api';
import { useAuthStore } from '../store/auth';

const API_BASE_URL = import.meta.env.VITE_API_URL || '/api';

// Check if we're in demo mode
const isDemoMode = () => {
  const token = useAuthStore.getState().token;
  return token?.startsWith('demo-token-') ?? false;
};

export const apiClient: AxiosInstance = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Request interceptor - add auth token
apiClient.interceptors.request.use(
  (config) => {
    const token = useAuthStore.getState().token;
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  },
  (error) => Promise.reject(error)
);

// Response interceptor - handle 401 (skip for demo mode)
apiClient.interceptors.response.use(
  (response) => response,
  (error: AxiosError) => {
    if (!isDemoMode() && error.response?.status === 401) {
      useAuthStore.getState().logout();
      window.location.href = '/login';
    }
    return Promise.reject(error);
  }
);

// Auth API
export const register = async (data: RegisterRequest): Promise<UserResponse> => {
  const response = await apiClient.post<UserResponse>('/auth/register', data);
  return response.data;
};

export const login = async (email: string, password: string): Promise<TokenResponse> => {
  const formData = new URLSearchParams();
  formData.append('username', email);
  formData.append('password', password);
  
  const response = await apiClient.post<TokenResponse>('/auth/login', formData, {
    headers: {
      'Content-Type': 'application/x-www-form-urlencoded',
    },
  });
  return response.data;
};

export const getMe = async (): Promise<UserResponse> => {
  const response = await apiClient.get<UserResponse>('/auth/me');
  return response.data;
};

// Vacancies API
export const getVacancies = async (): Promise<VacancyListItem[]> => {
  if (isDemoMode()) {
    return getMockVacancies();
  }
  const response = await apiClient.get<VacancyListItem[]>('/vacancies');
  return response.data;
};

export const getVacancy = async (id: number): Promise<VacancyResponse> => {
  if (isDemoMode()) {
    const vacancies = getMockVacancies();
    const vacancy = vacancies.find(v => v.id === id);
    if (vacancy) {
      return getMockVacancyResponse(id);
    }
    throw new Error('Vacancy not found');
  }
  const response = await apiClient.get<VacancyResponse>(`/vacancies/${id}`);
  return response.data;
};

export const uploadVacancy = async (file: File): Promise<VacancyResponse> => {
  if (isDemoMode()) {
    return getMockVacancyResponse(Date.now(), file.name);
  }
  const formData = new FormData();
  formData.append('file', file);
  
  const response = await apiClient.post<VacancyResponse>('/vacancies', formData, {
    headers: {
      'Content-Type': 'multipart/form-data',
    },
  });
  return response.data;
};

export const deleteVacancy = async (id: number): Promise<void> => {
  await apiClient.delete(`/vacancies/${id}`);
};

// Resumes API
export const getResumes = async (): Promise<ResumeListItem[]> => {
  if (isDemoMode()) {
    return getMockResumes();
  }
  const response = await apiClient.get<ResumeListItem[]>('/resumes');
  return response.data;
};

export const getResume = async (id: number): Promise<ResumeResponse> => {
  if (isDemoMode()) {
    const resumes = getMockResumes();
    const resume = resumes.find(r => r.id === id);
    if (resume) {
      return getMockResumeResponse(id);
    }
    throw new Error('Resume not found');
  }
  const response = await apiClient.get<ResumeResponse>(`/resumes/${id}`);
  return response.data;
};

export const uploadResume = async (file: File): Promise<ResumeResponse> => {
  if (isDemoMode()) {
    return getMockResumeResponse(Date.now(), file.name);
  }
  const formData = new FormData();
  formData.append('file', file);
  
  const response = await apiClient.post<ResumeResponse>('/resumes', formData, {
    headers: {
      'Content-Type': 'multipart/form-data',
    },
  });
  return response.data;
};

export const deleteResume = async (id: number): Promise<void> => {
  await apiClient.delete(`/resumes/${id}`);
};

// Matches API - endpoints NOT defined in OpenAPI spec yet (backend stub)
// TODO: add to backend and update paths when spec is ready
export const getMatchesForVacancy = async (id: number, top: number = 10): Promise<Match[]> => {
  if (isDemoMode()) {
    return getMockMatches();
  }
  // NOTE: endpoint not defined in OpenAPI - using demo mock
  console.warn('getMatchesForVacancy: real endpoint not implemented, using mock data');
  return getMockMatches();
};

export const getMatchesForResume = async (id: number, top: number = 10): Promise<Match[]> => {
  if (isDemoMode()) {
    return getMockMatches();
  }
  // NOTE: endpoint not defined in OpenAPI - using demo mock
  console.warn('getMatchesForResume: real endpoint not implemented, using mock data');
  return getMockMatches();
};

export const getOrphanVacancies = async (top: number = 10): Promise<VacancyListItem[]> => {
  if (isDemoMode()) {
    return getMockVacancies().slice(0, 2);
  }
  // NOTE: endpoint not defined in OpenAPI - using demo mock
  console.warn('getOrphanVacancies: real endpoint not implemented, using mock data');
  return getMockVacancies().slice(0, 2);
};

export const getOrphanResumes = async (top: number = 10): Promise<ResumeListItem[]> => {
  if (isDemoMode()) {
    return getMockResumes().slice(0, 2);
  }
  // NOTE: endpoint not defined in OpenAPI - using demo mock
  console.warn('getOrphanResumes: real endpoint not implemented, using mock data');
  return getMockResumes().slice(0, 2);
};

// Mock data for demo mode (based on demo_files)
function getMockVacancies(): VacancyListItem[] {
  return [
    { id: 1, title: 'Разработчик Rust (Middle+/Senior)', source_format: 'txt', location: 'Удаленно, по РФ', work_format: 'remote', created_at: new Date().toISOString() },
    { id: 2, title: 'Java-разработчик', source_format: 'txt', location: 'Удаленно', work_format: 'remote', created_at: new Date().toISOString() },
    { id: 3, title: 'Product owner CRM', source_format: 'txt', location: null, work_format: null, created_at: new Date().toISOString() },
    { id: 15, title: 'Frontend-разработчик', source_format: 'txt', location: null, work_format: null, created_at: new Date().toISOString() },
    { id: 20, title: 'Backend-разработчик (golang)', source_format: 'txt', location: null, work_format: null, created_at: new Date().toISOString() },
  ];
}

function getMockVacancyResponse(id?: number, customTitle?: string): VacancyResponse {
  const vacancyData: Record<number, VacancyResponse> = {
    1: {
      id: 1,
      owner_id: 0,
      title: 'Разработчик Rust (Middle+/Senior)',
      raw_text: 'Разработчик Rust (Middle+/Senior)\nУдаленно, по РФ\n\nОбязанности:\n• Разрабатывать и поддерживать бэкенд в условиях высокой нагрузки\n• Решать задачи, связанные с клиентской логикой и архитектурой приложения\n• Интегрировать бэкенд с другими сервисами\nТребования:\n• Знаете С++/Rust, алгоритмы и классические структуры данных\n• Коммерческий опыт работы от 4 лет\n• Умеете работать с STL, желательно с Boost\n• У вас есть опыт бэкенд-разработки и работы с высоконагруженными и многопоточными системами\n• Опыт работы с Kafka, Redis и PostgreSQL будет плюсом',
      source_format: 'txt',
      hard_skills: [
        { name: 'Rust', level: 'Middle/Senior', required: true },
        { name: 'C++', required: true },
        { name: 'STL', level: ' продвинутый' },
        { name: 'Boost' },
        { name: 'Kafka' },
        { name: 'Redis' },
        { name: 'PostgreSQL' },
      ],
      soft_skills: [
        { name: 'Архитектурное проектирование' },
        { name: 'Работа в команде' },
      ],
      experience: { years_min: 4, years_max: undefined, domains: ['Backend', 'Highload'] },
      location: 'Удаленно, по РФ',
      work_format: 'remote',
      work_hours: 'Полный день',
      other_requirements: { algorithms: true, data_structures: true },
      created_at: new Date().toISOString(),
    },
    2: {
      id: 2,
      owner_id: 0,
      title: 'Java-разработчик',
      raw_text: 'Java-разработчик\nУдаленно\n\nОбязанности:\n• Разрабатывать внешние и внутренние продукты\n• Прорабатывать и реализовать интеграционные решения\n• Писать код и проводить код-ревью\n• Писать тесты на свой код\n• Помогать менее опытным коллегам\nТребования:\n• Отлично знает Java от 11 версии, есть опыт коммерческой разработки на Java от 3 лет\n• Опыт работы с Kotlin\n• Опыт коммерческой разработки с любым из фреймворков: Spring Boot, Quarkus, Micronaut или Vert.x\n• Опыт коммерческой разработки с одним из контейнеризаторов: Kubernetes, Docker или OpenShift\n• Опыт коммерческой разработки с одним из брокеров: Kafka, Rabbit MQ или Active MQ\n• Опыт коммерческой разработки с Postgress, MySQL или Oracle\n• Опыт работы с системой контроля версий',
      source_format: 'txt',
      hard_skills: [
        { name: 'Java', level: 'от 11 версии', required: true },
        { name: 'Kotlin' },
        { name: 'Spring Boot' },
        { name: 'Kubernetes' },
        { name: 'Docker' },
        { name: 'Kafka' },
        { name: 'PostgreSQL' },
      ],
      soft_skills: [
        { name: 'Коммуникация' },
        { name: 'Менторство' },
      ],
      experience: { years_min: 3, years_max: undefined, domains: ['Backend', 'Integration'] },
      location: 'Удаленно',
      work_format: 'remote',
      work_hours: 'Полный день',
      other_requirements: { code_review: true, testing: true },
      created_at: new Date().toISOString(),
    },
    15: {
      id: 15,
      owner_id: 0,
      title: 'Frontend-разработчик',
      raw_text: 'Frontend-разработчик\n\nОбязанности:\n• Проект модернизации ЭДО. Команда Ядра ЭДО\n• Разработка фронта для внутренних пользователей на REACT.\nТребования:\n• TypeScript, JavaScript;\n• React;\n• Управление состояниями;\n• REST API;\n• HTML CSS;\n• Системы контроля версий (GIT);\n• Самостоятельность',
      source_format: 'txt',
      hard_skills: [
        { name: 'TypeScript', required: true },
        { name: 'JavaScript', required: true },
        { name: 'React', required: true },
        { name: 'State Management' },
        { name: 'REST API' },
        { name: 'HTML' },
        { name: 'CSS' },
        { name: 'Git' },
      ],
      soft_skills: [
        { name: 'Самостоятельность' },
        { name: 'Командная работа' },
      ],
      experience: { years_min: undefined, years_max: undefined, domains: ['Frontend'] },
      location: null,
      work_format: null,
      work_hours: null,
      other_requirements: {},
      created_at: new Date().toISOString(),
    },
    20: {
      id: 20,
      owner_id: 0,
      title: 'Backend-разработчик (golang)',
      raw_text: 'Backend-разработчик (golang)\n\nОбязанности:\n• Проектировать распределённые системы для одного из продуктовых доменов;\n• Участвовать в рефакторинге существующего кода и разрабатывать новые сервисы на Go;\n• Развивать API и принимать активное участие в жизни в кросс-функциональной продуктовой команды.\nТребования:\n• Коммерческий опыт владения Go от 4-х лет;\n• Коммерческий опыт владения PHP от 1-го года;\n• Желание принимать активное участие в рефакторинге существующего кода для ключевых проектов и написании нового на Go (Go - 80% и PHP - 20%);\n• Имеете опыт в разработке высоконагруженных систем;\n• Командный игрок, готовый к коммуникации со смежными командами;\n• Наличие технического образования - приветствуется.',
      source_format: 'txt',
      hard_skills: [
        { name: 'Go', level: 'от 4 лет', required: true },
        { name: 'PHP', level: 'от 1 года', required: true },
        { name: 'Distributed Systems' },
        { name: 'Highload' },
      ],
      soft_skills: [
        { name: 'Командная работа' },
        { name: 'Коммуникация' },
        { name: 'Рефакторинг' },
      ],
      experience: { years_min: 4, years_max: undefined, domains: ['Backend', 'Distributed Systems'] },
      location: null,
      work_format: null,
      work_hours: null,
      other_requirements: { technical_education: 'preferred' },
      created_at: new Date().toISOString(),
    },
  };

  return vacancyData[id || 1] || vacancyData[1];
}

function getMockResumes(): ResumeListItem[] {
  return [
    { id: 1, candidate_name: 'Кандидат 1 (Senior C++/Rust)', source_format: 'txt', location: null, preferred_work_format: null, created_at: new Date().toISOString() },
    { id: 2, candidate_name: 'Кандидат 2 (Backend Rust)', source_format: 'txt', location: null, preferred_work_format: null, created_at: new Date().toISOString() },
    { id: 3, candidate_name: 'Кандидат 3 (Java Senior)', source_format: 'txt', location: null, preferred_work_format: null, created_at: new Date().toISOString() },
    { id: 10, candidate_name: 'Кандидат 10 (QA Automation)', source_format: 'txt', location: null, preferred_work_format: null, created_at: new Date().toISOString() },
    { id: 15, candidate_name: 'Кандидат 15 (Frontend React)', source_format: 'txt', location: null, preferred_work_format: null, created_at: new Date().toISOString() },
  ];
}

function getMockResumeResponse(id?: number, customName?: string): ResumeResponse {
  const resumeData: Record<number, ResumeResponse> = {
    1: {
      id: 1,
      owner_id: 0,
      candidate_name: 'Кандидат 1',
      raw_text: 'Senior software developer C++/Rust\n\nПрофессиональный опыт\nООО "Л"\nSenior software developer C++/Rust\nНоябрь 2021 — Февраль 2026 (4 года 4 месяца)\nРазрабатывал библиотеку для отображения графической части торгового терминала. Большой проект на C++. Руководство небольшой командой.\nОсновные технологии: C++20, Rust, Bevy, SKIA, CMake, Conan, OpenGL, GLSL, Metal, Flatbuffers, JNI, WASM. GoogleTest, Jira, Gitlab, Docker, Python',
      source_format: 'txt',
      hard_skills: [
        { name: 'C++', level: 'Senior', required: true },
        { name: 'Rust', level: 'Senior', required: true },
        { name: 'OpenGL' },
        { name: 'GLSL' },
        { name: 'Metal' },
        { name: 'Docker' },
      ],
      soft_skills: [
        { name: 'Team leadership' },
        { name: 'Architecture decisions' },
      ],
      experience: { total_years: 14, positions: ['Senior Software Developer', 'Team Lead'], domains: ['Trading', 'Graphics', 'Embedded'] },
      location: null,
      preferred_work_format: null,
      other_traits: { languages: ['Английский B2'] },
      created_at: new Date().toISOString(),
    },
    2: {
      id: 2,
      owner_id: 0,
      candidate_name: 'Кандидат 2',
      raw_text: 'Backend-разработчик\n\nПрофессиональный опыт\nООО\nBackend-разработчик\nФевраль 2024 — по настоящее время (2 года 3 месяца)\nРазрабатывал и развёртывал backend-сервисы на Rust (Tokio, Axum, SQLx) и Node.js (NestJS, Drizzle ORM).\nКлючевые проекты: система мониторинга домофонов (80 000 пользователей), сканер уязвимостей.\nТехнологии: rust, axum, sqlx, Node.js, NestJS, PostgreSQL, Docker, Kafka, Pyo3',
      source_format: 'txt',
      hard_skills: [
        { name: 'Rust', level: 'Middle+', required: true },
        { name: 'Node.js' },
        { name: 'PostgreSQL' },
        { name: 'Docker' },
        { name: 'Kafka' },
        { name: 'Axum' },
        { name: 'NestJS' },
      ],
      soft_skills: [
        { name: 'Самостоятельная работа' },
        { name: 'DDD подход' },
      ],
      experience: { total_years: 2, positions: ['Backend Developer'], domains: ['Backend', 'SaaS'] },
      location: null,
      preferred_work_format: null,
      other_traits: { languages: ['Английский B1'] },
      created_at: new Date().toISOString(),
    },
    3: {
      id: 3,
      owner_id: 0,
      candidate_name: 'Кандидат 3',
      raw_text: 'Старший программист\n\nПрофессиональный опыт\nООО\nСтарший программист\nОктябрь 2024 — по настоящее время (1 год 7 месяцев)\nCVM (Customer Value Management) для Hoff. Архитектура: микросервисы, высокая нагрузка.\nДостижения: устранение утечки памяти, шаблонизирующий сервис на Thymeleaf, exactly-once delivery модель.\nТехнологии: Java 17, Spring Boot, Kafka, PostgreSQL, Greenplum, Kubernetes\n\nБанк\nИнженер-программист\nМай 2023 — Октябрь 2024 (1 год 6 месяцев)\nКазначейство ГПБ. 3млн банковских документов в сутки.\nТехнологии: Kotlin, Java 17, SpringBoot, PostgreSQL/YandexDB, Docker, Camunda',
      source_format: 'txt',
      hard_skills: [
        { name: 'Java', level: 'Senior', required: true },
        { name: 'Kotlin', required: true },
        { name: 'Spring Boot' },
        { name: 'Kafka' },
        { name: 'PostgreSQL' },
        { name: 'Kubernetes' },
        { name: 'Camunda' },
      ],
      soft_skills: [
        { name: 'Technical Leadership' },
        { name: 'Code Review' },
        { name: 'Mentoring' },
      ],
      experience: { total_years: 6, positions: ['Senior Programmer', 'Tech Lead'], domains: ['Fintech', 'E-commerce', 'Banking'] },
      location: null,
      preferred_work_format: null,
      other_traits: { languages: ['Английский B2'] },
      created_at: new Date().toISOString(),
    },
    10: {
      id: 10,
      owner_id: 0,
      candidate_name: 'Кандидат 10',
      raw_text: 'QA Automation\n\nПрофессиональный опыт\nООО\nQA Automation\nАвгуст 2023 — настоящее время (2 года 9 месяцев)\nПроект Yappy (мобильное приложение). Команда мобильного тестирования (android/ios).\nСтек: Python 3.10, Pytest, Poco, Airtest, pytest-bdd\n\nООО\nИнженер по автоматизации тестирования\nСентябрь 2021 — Август 2023\nРазработка фреймворка на Python 3.8, Selenium, Pytest, Requests.\n\nНавыки: QA, Python, Selenium, Pytest, Git, Linux, REST API, SQL',
      source_format: 'txt',
      hard_skills: [
        { name: 'Python', level: 'Senior', required: true },
        { name: 'Selenium' },
        { name: 'Pytest' },
        { name: 'REST API Testing' },
        { name: 'Git' },
        { name: 'SQL' },
      ],
      soft_skills: [
        { name: 'Внимание к деталям' },
        { name: 'Документация' },
      ],
      experience: { total_years: 12, positions: ['QA Automation', 'Test Engineer'], domains: ['Mobile', 'E2E Testing'] },
      location: null,
      preferred_work_format: null,
      other_traits: { languages: ['Английский A2'] },
      created_at: new Date().toISOString(),
    },
    15: {
      id: 15,
      owner_id: 0,
      candidate_name: 'Кандидат 15',
      raw_text: 'Frontend-разработчик (React.js, Redux, Typescript)\n\nБанк\nFrontend-разработчик\nИюнь 2025 — по настоящее время (11 месяцев)\nB2B-платформа Альфа-Банка. SSR-приложение, микрофронтенд-архитектура (module federation).\nStack: React.js, JavaScript, TypeScript, Webpack, Redux Toolkit, Microfrontends, Event-bus.\n\nФИнтех\nFrontend-разработчик\nОктябрь 2022 — Апрель 2025 (2 года 7 месяцев)\nТорговая Платформа СПВБ. 2000+ пользователей.\nStack: React.js, Redux, RTK Query, Antd, Chart.js, Socket.io.\n\nООО\nFrontend-разработчик\nМарт 2021 — Август 2022 (1 год 6 месяцев)\nCRM-система Optilogs. React-yandex-map, Material UI.\n\nНавыки: JavaScript, TypeScript, React, Redux, REST API, Webpack, Jest, Cypress',
      source_format: 'txt',
      hard_skills: [
        { name: 'React', level: 'Senior', required: true },
        { name: 'TypeScript', level: 'Senior', required: true },
        { name: 'Redux' },
        { name: 'Microfrontends' },
        { name: 'Webpack' },
        { name: 'Jest' },
        { name: 'Cypress' },
        { name: 'Playwright' },
      ],
      soft_skills: [
        { name: 'Mentoring' },
        { name: 'Architecture decisions' },
        { name: 'Code Review' },
      ],
      experience: { total_years: 5, positions: ['Frontend Developer', 'Tech Mentor'], domains: ['Fintech', 'Banking', 'Logistics'] },
      location: null,
      preferred_work_format: null,
      other_traits: { languages: ['Английский B1'] },
      created_at: new Date().toISOString(),
    },
  };

  return resumeData[id || 1] || resumeData[1];
}

function getMockMatches(): Match[] {
  return [
    {
      id: 1,
      vacancy_id: 1,
      resume_id: 1,
      score: 95,
      explanation: 'Отличное совпадение. Кандидат имеет 14+ лет опыта с C++ и Rust на Senior уровне, опыт работы с высоконагруженными системами и многопоточностью полностью соответствует требованиям вакансии.',
      missing_skills: ['Kafka, Redis (указаны как плюс)'],
      matching_skills: ['Rust', 'C++', 'STL', 'Boost', 'Многопоточные системы', 'Highload'],
      computed_at: new Date().toISOString(),
      candidate_name: 'Кандидат 1',
      vacancy_title: 'Разработчик Rust (Middle+/Senior)',
    },
    {
      id: 2,
      vacancy_id: 1,
      resume_id: 2,
      score: 82,
      explanation: 'Хорошее совпадение. Кандидат имеет опыт с Rust и бэкенд-разработкой, но меньший опыт (2+ года против требуемых 4+ лет). Знание Kafka и PostgreSQL соответствует требованиям.',
      missing_skills: ['Опыт 4+ лет (есть 2+ года)', 'STL/Boost'],
      matching_skills: ['Rust', 'Backend development', 'Kafka', 'PostgreSQL'],
      computed_at: new Date().toISOString(),
      candidate_name: 'Кандидат 2',
      vacancy_title: 'Разработчик Rust (Middle+/Senior)',
    },
    {
      id: 3,
      vacancy_id: 2,
      resume_id: 3,
      score: 88,
      explanation: 'Хорошее совпадение. Кандидат имеет 6+ лет опыта с Java, опыт работы с Spring Boot, Kafka, PostgreSQL. Соответствует большинству требований вакансии.',
      missing_skills: ['Kotlin (указан как плюс, есть у кандидата)'],
      matching_skills: ['Java 17', 'Spring Boot', 'Kafka', 'PostgreSQL', 'Kubernetes', 'Docker'],
      computed_at: new Date().toISOString(),
      candidate_name: 'Кандидат 3',
      vacancy_title: 'Java-разработчик',
    },
    {
      id: 4,
      vacancy_id: 15,
      resume_id: 15,
      score: 97,
      explanation: 'Отличное совпадение! Кандидат имеет 5+ лет опыта с React и TypeScript на Senior уровне, опыт работы с state management, REST API полностью соответствует требованиям.',
      missing_skills: [],
      matching_skills: ['React', 'TypeScript', 'JavaScript', 'State Management', 'REST API', 'Git'],
      computed_at: new Date().toISOString(),
      candidate_name: 'Кандидат 15',
      vacancy_title: 'Frontend-разработчик',
    },
    {
      id: 5,
      vacancy_id: 20,
      resume_id: 2,
      score: 72,
      explanation: 'Среднее совпадение. Кандидат имеет опыт с Rust и бэкенд-разработкой, но вакансия требует Go. Опыт разработки высоконагруженных систем соответствует.',
      missing_skills: ['Go (есть Rust)', 'PHP'],
      matching_skills: ['Backend', 'Highload', 'Distributed Systems'],
      computed_at: new Date().toISOString(),
      candidate_name: 'Кандидат 2',
      vacancy_title: 'Backend-разработчик (golang)',
    },
  ];
}
