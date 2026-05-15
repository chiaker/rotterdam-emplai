# План: ИИ-ассистент рекрутера (продвинутый уровень)

## Context

Хакатон-задача — разработать сервис, который автоматизирует первичный отбор кандидатов: парсит вакансии и резюме (txt/pdf/docx), извлекает структурированные сущности (хард/софт-скиллы, опыт, локация, формат работы), хранит их в БД с возможностью поиска и выдаёт ранжированные мэтчинги с обоснованием ≥85%. Цель — попасть в **продвинутый уровень**: REST API + Swagger + аутентификация + парсинг всех трёх форматов + БД + русскоязычная LLM + веб-UI + Docker Compose.

Стек зафиксирован: **FastAPI**, **PostgreSQL**, **Anthropic Claude Opus 4.7** (`claude-opus-4-7`), **React + Vite + Tailwind**, **JWT-auth с регистрацией рекрутёров**, **без эмбеддингов на старте**. Каталог `c:\p\hakaton` пустой — greenfield.

### Известные риски / компромиссы
- **Русскоязычная модель**: критерий гласит «русскоязычная модель ИИ (например, GigaChat)». Claude мультиязычная и отлично работает с русским, но формально не «русскоязычная». Решено идти с Claude — в README отдельно зафиксировать аргумент про мультиязычность и качество.
- **Без эмбеддингов**: матчинг 1 вакансия × N резюме упирается в стоимость LLM-вызовов. Решаем двухступенчатым пайплайном: SQL-пре-фильтр по пересечению структурированных скиллов → LLM-скоринг только top-K. Это даёт устойчивый «не полным перебором в памяти» (критерий 6 medium-уровня).

## Архитектура

```
hakaton/
├── backend/                    # FastAPI + Typer CLI
│   ├── app/
│   │   ├── main.py             # FastAPI приложение, роутеры, exception handlers
│   │   ├── cli.py              # Typer CLI (базовый уровень: --help, ingest, match)
│   │   ├── core/
│   │   │   ├── config.py       # pydantic-settings, .env
│   │   │   ├── security.py     # bcrypt + python-jose (JWT)
│   │   │   └── deps.py         # get_db, get_current_user
│   │   ├── db/
│   │   │   ├── session.py      # AsyncSession + engine
│   │   │   └── models.py       # SQLAlchemy 2.0 модели
│   │   ├── schemas/            # Pydantic v2 (req/resp/доменные)
│   │   ├── api/
│   │   │   ├── auth.py         # /auth/register, /auth/login
│   │   │   ├── vacancies.py    # /vacancies CRUD + upload
│   │   │   ├── resumes.py      # /resumes CRUD + upload
│   │   │   └── matches.py      # все 4 типа выдачи (см. ниже)
│   │   └── services/
│   │       ├── parser.py       # txt/pdf/docx → текст (pypdf, python-docx)
│   │       ├── claude.py       # клиент Anthropic с prompt caching
│   │       ├── extractor.py    # извлечение сущностей через Claude tool_use
│   │       ├── matcher.py      # пре-фильтр + LLM-скоринг + кэш
│   │       └── repository.py   # запросы к БД (JSONB-операторы)
│   ├── alembic/                # миграции
│   ├── tests/                  # pytest + httpx
│   ├── pyproject.toml
│   └── Dockerfile
├── frontend/                   # React 18 + Vite + Tailwind
│   ├── src/
│   │   ├── main.tsx, App.tsx
│   │   ├── api/client.ts       # axios + JWT interceptor
│   │   ├── store/auth.ts       # Zustand: token, user
│   │   ├── pages/
│   │   │   ├── Login.tsx, Register.tsx
│   │   │   ├── Vacancies.tsx, VacancyDetail.tsx
│   │   │   ├── Resumes.tsx, ResumeDetail.tsx
│   │   │   └── Matches.tsx     # 4 вкладки: top-N, top-K, vac-no-cand, cand-no-vac
│   │   └── components/         # UploadDropzone, MatchCard, SkillBadge, ...
│   ├── nginx.conf
│   ├── package.json
│   └── Dockerfile              # multi-stage: build → nginx serve
├── demo/
│   ├── postman_collection.json
│   ├── curl_examples.sh
│   ├── sample_vacancies/       # 5-10 файлов txt/pdf/docx на русском
│   └── sample_resumes/         # 20-30 файлов
├── docker-compose.yml
├── .env.example
└── README.md
```

## Модель данных (PostgreSQL)

```sql
users(id PK, email UNIQUE, hashed_password, created_at)

vacancies(
  id PK, owner_id FK→users, title, raw_text, source_format,
  hard_skills jsonb,      -- [{name, level, required}]
  soft_skills jsonb,
  experience jsonb,       -- {years_min, years_max, domains[]}
  location, work_format,  -- remote/office/hybrid
  work_hours,
  other_requirements jsonb,
  created_at
)

resumes(
  id PK, owner_id FK→users, candidate_name, raw_text, source_format,
  hard_skills jsonb, soft_skills jsonb,
  experience jsonb,       -- {total_years, positions[]}
  location, preferred_work_format,
  other_traits jsonb,
  created_at
)

matches(                  -- кэш скоринга, чтоб не пересчитывать
  id PK,
  vacancy_id FK, resume_id FK,
  score smallint,         -- 0..100
  explanation text,       -- русское обоснование
  missing_skills jsonb,
  matching_skills jsonb,
  computed_at,
  UNIQUE(vacancy_id, resume_id)
)
```

Индексы: GIN по `hard_skills`, обычные по `owner_id`, `(vacancy_id, score)`, `(resume_id, score)`.

## REST API (OpenAPI/Swagger на `/docs`)

| Метод | Путь | Назначение |
|---|---|---|
| POST | `/api/auth/register` | регистрация рекрутёра |
| POST | `/api/auth/login` | JWT access-token |
| GET  | `/api/auth/me` | текущий пользователь |
| POST | `/api/vacancies` | загрузка файла (multipart) → парсинг → extractor → сохранение |
| GET  | `/api/vacancies` | список |
| GET  | `/api/vacancies/{id}` | детали + извлечённые сущности |
| DELETE | `/api/vacancies/{id}` | |
| POST | `/api/resumes` | то же для резюме |
| GET  | `/api/resumes`, `/api/resumes/{id}`, DELETE | |
| GET  | `/api/matches/vacancy/{id}?top=N` | топ-N кандидатов под вакансию с обоснованием, ≥85% |
| GET  | `/api/matches/resume/{id}?top=K` | топ-K вакансий под кандидата, ≥85% |
| GET  | `/api/matches/orphan-vacancies?top=X` | вакансии, у которых все мэтчи <85% |
| GET  | `/api/matches/orphan-resumes?top=Y` | кандидаты, у которых все мэтчи <85% |

Все ручки кроме `/auth/*` — за `Bearer` JWT.

## Пайплайн матчинга (без эмбеддингов)

1. **При загрузке** вакансии/резюме: `parser` → текст → `extractor` вызывает Claude с **structured output через tool_use** (Pydantic-схема) → JSONB сохраняется в БД.
2. **При запросе матча**:
   - SQL-пре-фильтр в `repository`: жёсткие требования (локация если задана, формат работы), затем сортировка по пересечению `hard_skills` через JSONB-операторы (`?|`, `@>`) → берём ~30 кандидатов.
   - Параллельный LLM-скоринг через `asyncio.gather` (батчи по 5): на каждого Claude возвращает `{score, explanation, missing_skills, matching_skills}` через tool_use.
   - Фильтр `score ≥ 85`, сортировка по убыванию, top-N.
   - Запись в `matches` (UPSERT) → последующие запросы дёшёвые.
3. **Orphan-эндпоинты**: SQL-агрегации по `matches` (`HAVING MAX(score) < 85`), без LLM.

## Защита от галлюцинаций

- **Structured output (tool_use)**: Claude обязан вернуть JSON по Pydantic-схеме, не свободный текст.
- **System prompt** (закэшированный через `cache_control`) явно запрещает выдумывать факты — каждый missing_skill должен ссылаться на отсутствие в тексте резюме.
- В обосновании Claude обязан цитировать фрагменты исходных текстов (поле `citations: [{source: "vacancy"|"resume", quote: "..."}]`).
- При невалидном выводе LLM — повтор 1 раз, потом отдаём 200 с `score=null, error="extraction failed"` (не 500).

## Аутентификация

- bcrypt для паролей, `python-jose` для JWT (HS256, секрет в `.env`).
- access-token 24 часа, без refresh — для хакатона хватит.
- Регистрация открытая (для демо), в README отметить флаг `REGISTRATION_ENABLED`.
- Фронт: после логина token в `localStorage`, axios-interceptor шлёт `Authorization: Bearer ...`.

## CLI (закрывает базовый уровень)

`python -m app.cli --help` → справка по командам:
- `ingest-vacancy <path>` — парсит txt и кладёт в БД (или файл, если флаг `--no-db`).
- `ingest-resume <path>`
- `match-vacancy <id> --top N`
- `match-resume <id> --top K`
- `demo` — прогон демо-скрипта на семплах из `demo/`.

CLI импортирует те же `services/*` напрямую → нет дублирования логики, БД не обязательна для базового уровня (флаг файлового хранилища).

## Веб-UI

- **Login/Register** — формы, валидация, ошибки.
- **Vacancies / Resumes** — список + dropzone-загрузка (drag&drop), модалка с деталями и извлечёнными сущностями (badges по скиллам).
- **Matches** — 4 вкладки (top-N под вакансию, top-K под кандидата, orphan-vacancies, orphan-resumes); карточки с прогресс-баром скоринга, развёрнутым обоснованием и списком missing skills.
- **Адаптив**: Tailwind breakpoints (`sm/md/lg`), сетка из `grid-cols-1 md:grid-cols-2 lg:grid-cols-3`, мобильное меню гамбургером — закрывает бонусный пункт.

## Docker Compose

```yaml
services:
  db:        # postgres:16-alpine, volume, healthcheck
  backend:   # build ./backend, depends_on db (healthy), порт 8000
  frontend:  # build ./frontend (multi-stage nginx), порт 5173 → 80
```

`.env.example` с `ANTHROPIC_API_KEY`, `POSTGRES_*`, `JWT_SECRET`, `BACKEND_CORS_ORIGINS`.

## Демо-материалы (`demo/`)

- **Postman-коллекция**: register → login → upload vacancy → upload resumes → match.
- **curl_examples.sh**: те же сценарии в bash/PowerShell.
- **sample_vacancies/**: 5-10 файлов на русском, перекрывающие txt/pdf/docx.
- **sample_resumes/**: 20-30 — часть должна релевантно матчиться (>85%), часть нет (для проверки orphan-эндпоинтов).
- **README**: quick start (3 команды), ссылки на Swagger и UI.

## Стабильность (no-500)

- Глобальный `exception_handler` в FastAPI → отдаёт `{error, detail}` с кодом 4xx.
- В сервисах: ошибки парсинга → 422 «не удалось разобрать файл», ошибки Claude → 503 «AI временно недоступен», валидация — 400.
- Tenacity-ретраи для Claude (3 попытки, экспоненциальная задержка).

## Критичные файлы для создания

| Файл | Назначение |
|---|---|
| [backend/app/main.py](backend/app/main.py) | FastAPI app, CORS, роутеры, exception handlers |
| [backend/app/core/config.py](backend/app/core/config.py) | Settings из .env |
| [backend/app/core/security.py](backend/app/core/security.py) | bcrypt, JWT encode/decode |
| [backend/app/db/models.py](backend/app/db/models.py) | SQLAlchemy модели |
| [backend/app/services/parser.py](backend/app/services/parser.py) | txt/pdf/docx → text |
| [backend/app/services/claude.py](backend/app/services/claude.py) | Anthropic клиент + prompt caching |
| [backend/app/services/extractor.py](backend/app/services/extractor.py) | tool_use → структурированные сущности |
| [backend/app/services/matcher.py](backend/app/services/matcher.py) | пре-фильтр + LLM-скоринг + кэш |
| [backend/app/services/repository.py](backend/app/services/repository.py) | SQL-запросы, JSONB-операторы |
| [backend/app/api/matches.py](backend/app/api/matches.py) | 4 эндпоинта выдачи |
| [backend/app/cli.py](backend/app/cli.py) | Typer CLI для базового уровня |
| [frontend/src/pages/Matches.tsx](frontend/src/pages/Matches.tsx) | главный экран с 4 вкладками |
| [docker-compose.yml](docker-compose.yml) | оркестрация |
| [README.md](README.md) | quick start, аргументация по Claude, скоринговая методика |

## Используемые библиотеки

**Backend**: `fastapi`, `uvicorn[standard]`, `pydantic`, `pydantic-settings`, `sqlalchemy[asyncio]`, `asyncpg`, `alembic`, `python-jose[cryptography]`, `passlib[bcrypt]`, `python-multipart`, `pypdf`, `python-docx`, `anthropic`, `typer[all]`, `tenacity`, `pytest`, `httpx`.

**Frontend**: `react`, `react-dom`, `react-router-dom`, `axios`, `zustand`, `tailwindcss`, `@hookform/resolvers`, `react-hook-form`, `zod`, `lucide-react`.

## План верификации (end-to-end)

1. `cp .env.example .env`, прописать `ANTHROPIC_API_KEY`.
2. `docker compose up --build` → ждём healthy у `db`, `backend`, `frontend`.
3. Открыть `http://localhost:8000/docs` → Swagger со всеми эндпоинтами.
4. Через UI (`http://localhost:5173`):
   - регистрация → логин → JWT в storage.
   - Загрузить 1 вакансию (pdf) и 5 резюме (по 1 txt/pdf/docx, остальные txt).
   - Вкладка Matches → top-N кандидатов: проверить, что у каждого `score ≥ 85`, есть русское обоснование, список missing skills, не выдумано (сверяем с исходником).
   - Загрузить заведомо нерелевантное резюме → проверить orphan-resumes.
   - Создать вакансию без подходящих → проверить orphan-vacancies.
5. CLI: `docker compose exec backend python -m app.cli --help`, `python -m app.cli demo` — прогон полного цикла на семплах.
6. Postman-коллекция: импорт, запустить все запросы, проверить отсутствие 500 на негативе (битый pdf, пустой файл, плохой токен, несуществующий id).
7. Адаптив: открыть UI в DevTools на ширинах 375/768/1280 — макет корректный.
8. Проверка качества: на семпле из 10 размеченных пар (релевантных/нет) посчитать долю корректных вердиктов ≥85% → цель 80%+ для максимума баллов (20 баллов по критерию 9 базового уровня).
