npm install
npm run dev -- --host 0.0.0.0

__Эндпоинты по спецификации (совпадают):__

- Auth: `/api/auth/register`, `/api/auth/login`, `/api/auth/me` — ок
- Vacancies: `/api/vacancies`, `/api/vacancies/{id}` — ок
- Resumes: `/api/resumes`, `/api/resumes/{id}` — ок

__Matches эндпоинты НЕ определены в OpenAPI__ — соответственно, функции `getMatchesForVacancy`, `getMatchesForResume`, `getOrphanVacancies`, `getOrphanResumes` теперь возвращают mock-данные с предупреждением в консоли (вместо падающего запроса на несуществующий backend).

Страница "Мэтчи" продолжит работать в demo-режиме, а при подключении к реальному API покажет данные из mock-функций. Когда бэкенд добавит эндпоинты `/api/matches/*` — нужно будет обновить и спецификацию, и client.ts.
