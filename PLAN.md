# План: ИИ-ассистент рекрутера (продвинутый уровень)

## Context

Хакатон-задача — разработать сервис, который автоматизирует первичный отбор кандидатов: парсит вакансии и резюме (txt/pdf/docx), извлекает структурированные сущности (хард/софт-скиллы, опыт, локация, формат работы), хранит их в БД с возможностью поиска и выдаёт ранжированные мэтчинги с обоснованием ≥85%. Цель — попасть в **продвинутый уровень**: REST API + Swagger + аутентификация + парсинг всех трёх форматов + БД + русскоязычная LLM + веб-UI + Docker Compose.

Стек зафиксирован: **FastAPI**, **PostgreSQL + pgvector**, **GigaChat Embeddings**, **Anthropic Claude Opus 4.7** (`claude-opus-4-7`), **React + Vite + Tailwind**, **JWT-auth с регистрацией рекрутёров**. Каталог `c:\p\hakaton` пустой — greenfield.

### Известные риски / компромиссы
- **Русскоязычная модель**: критерий гласит «русскоязычная модель ИИ (например, GigaChat)». Берём **GigaChat Embeddings** для семантики (закрывает критерий) и **Claude Opus 4.7** для скоринга/обоснования (даёт качество). В README зафиксировать роли моделей.
- **Векторный матчинг** (пересмотрено, ранее «без эмбеддингов»): keyword-overlap по JSONB не ловит синонимы ("Python" vs "питон") и повествовательное описание опыта. Переходим на трёхступенчатый пайплайн: **vector pre-filter (pgvector) → hard filter (SQL по структурным полям) → Claude scoring top-K**. Подробности — в разделе [Этап 2 — Векторный матчинг (детальный план)](#этап-2--векторный-матчинг-детальный-план) ниже.

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

---

## Этап 2 — Векторный матчинг (детальный план)

### Зачем пивот

Этап 1 завершён: фундамент бэкенда работает (auth, парсер, CRUD), JSONB-поля пустые. Изначальный план предполагал двухступенчатый матчинг «SQL-префильтр по пересечению скиллов → LLM-скоринг» **без эмбеддингов**. Пересматриваем: добавляем векторную БД для семантического префильтра. Причины:

- Пересечение `hard_skills` через JSONB-операторы зависит от точного совпадения формулировок ("Python" ≠ "питон" ≠ "Python 3"). Эмбеддинги нивелируют это.
- Резюме часто описывают опыт повествовательно ("разрабатывал e-commerce платформу на Django"), а вакансия требует структурно ("Python, Django, опыт e-commerce"). Семантический матчинг ловит такие соответствия лучше keyword-based.
- **GigaChat Embeddings** одновременно закрывает критерий хакатона «русскоязычная модель ИИ (например, GigaChat)» — Claude остаётся для скоринга и обоснования, GigaChat легитимизирует «русскость» решения.

**Зафиксированные решения**:
- Векторная БД: **pgvector** в существующем Postgres 16 (один сервис, транзакции вместе с JSONB).
- Эмбеддинги: **GigaChat Embeddings** через официальный SDK (`gigachat` Python).
- Чанкирование: **гибрид** — 1 «обзорный» вектор на документ + отдельные векторы по семантическим секциям (skills, experience).

### Архитектура (high-level)

```
Upload файла (vacancy/resume)
   │
   ├─► parser.py       (txt/pdf/docx → text)            [Stage 1, есть]
   ├─► extractor.py    (Claude tool_use → JSONB)         [NEW]
   ├─► embedder.py     (GigaChat → vector(1024) × 3)     [NEW]
   └─► repository.py   (INSERT row + vectors)            [extend]

Match request (vacancy → top-N resumes)
   │
   ├─► [1] Vector pre-filter  (pgvector: top-30 by hybrid cosine sim)
   ├─► [2] Hard filter         (SQL: location, work_format, skill-overlap ≥1)
   ├─► [3] LLM scoring         (Claude tool_use parallel, top-15 → score 0-100)
   ├─► Filter score ≥ 85, sort desc, top-N
   └─► UPSERT в matches (кэш) → ответ
```

### Источники истины и потоки данных

| Данное | Источник | Когда вычисляется |
|---|---|---|
| `raw_text` | парсер | при upload, один раз |
| `hard_skills`, `soft_skills`, `experience`, `location`, `work_format`, ... | Claude extractor | при upload, один раз |
| `embedding_doc`, `embedding_skills`, `embedding_experience` | GigaChat | при upload, один раз |
| Match score / explanation | Claude matcher | при первом запросе пары (vac, res), кэш в `matches` |

**Инвариант**: эмбеддинги пересчитываются только при изменении `raw_text` (т.е. практически никогда — у нас нет edit-эндпоинта). Это критично для квоты GigaChat.

### Данные и схема (pgvector)

#### Расширение Postgres
Меняем образ в `docker-compose.yml`:
```yaml
db:
  image: pgvector/pgvector:pg16   # вместо postgres:16-alpine
```
`pgvector/pgvector:pg16` основан на стандартном postgres:16, добавляет prebuilt `vector` extension.

#### Alembic-миграция №2 (`add_vector_columns`)
```sql
CREATE EXTENSION IF NOT EXISTS vector;

ALTER TABLE vacancies
  ADD COLUMN embedding_doc        vector(1024),
  ADD COLUMN embedding_skills     vector(1024),
  ADD COLUMN embedding_experience vector(1024),
  ADD COLUMN extraction_status    varchar(16) NOT NULL DEFAULT 'pending';

ALTER TABLE resumes
  ADD COLUMN embedding_doc        vector(1024),
  ADD COLUMN embedding_skills     vector(1024),
  ADD COLUMN embedding_experience vector(1024),
  ADD COLUMN extraction_status    varchar(16) NOT NULL DEFAULT 'pending';

CREATE INDEX ix_vacancies_embedding_doc_hnsw
  ON vacancies USING hnsw (embedding_doc vector_cosine_ops);
CREATE INDEX ix_resumes_embedding_doc_hnsw
  ON resumes USING hnsw (embedding_doc vector_cosine_ops);
```

- `vector(1024)` — GigaChat Embeddings возвращает 1024-мерный вектор (модель `Embeddings`).
- `extraction_status ∈ {pending, ok, failed}` — нужен потому что extractor может упасть (квота/невалидный JSON), а доку всё равно сохраняем по raw_text.
- HNSW предпочтительнее IVFFlat: не требует `ANALYZE`-step и работает на пустых таблицах. На хакатон-объёмах (100-1000 строк) индексы на section-vectors избыточны — добавим если EXPLAIN покажет full scan.

#### Изменения в `app/db/models.py`
Импортируем `from pgvector.sqlalchemy import Vector`, добавляем 3 колонки `Mapped[list[float] | None] = mapped_column(Vector(1024), nullable=True)` и `extraction_status: Mapped[str]`. Аналогично для `Resume`.

#### Зависимости
В `backend/pyproject.toml`:
- `pgvector>=0.3` — Python-биндинги для SQLAlchemy
- `gigachat>=0.1.32` — официальный SDK Сбера

### Конвейер парсинга текста

Парсер из Этапа 1 (`services/parser.py`) уже работает корректно для txt/pdf/docx и возвращает `(text, source_format)`. **Расширений не требуется** на этом этапе. После парсинга `raw_text` идёт в extractor и embedder последовательно (extractor первый, его выход формирует чанки для embedder'а).

Если в будущем потребуется лучшее качество (OCR для сканов PDF, обработка таблиц в docx) — отдельный этап.

### Извлечение сущностей через Claude (tool_use)

#### Зачем
GigaChat считает эмбеддинги, но **структурированные поля** (skills, experience, location) нужны для:
- Точного hard-filter в SQL.
- Отображения badges в UI.
- Передачи в Claude-matcher как структурированного контекста (улучшает обоснование).
- Подсчёта `matching_skills`/`missing_skills` для ответа.

#### Pydantic-схемы tool_use

```python
class VacancyExtraction(BaseModel):
    title: str                          # уточнённый title из текста
    hard_skills: list[Skill]            # [{name, level: junior|middle|senior|expert|null, required: bool}]
    soft_skills: list[str]
    experience: ExperienceRequirement   # {years_min, years_max | null, domains: [str]}
    location: str | None                # "Москва" / "Remote" / null
    work_format: Literal["remote","office","hybrid"] | None
    work_hours: str | None
    other_requirements: dict[str, Any]

class ResumeExtraction(BaseModel):
    candidate_name: str | None
    hard_skills: list[Skill]
    soft_skills: list[str]
    experience: CandidateExperience     # {total_years, positions: [{title, company, years, description}]}
    location: str | None
    preferred_work_format: Literal["remote","office","hybrid"] | None
    other_traits: dict[str, Any]
```

#### Как вызываем Claude
- Single tool definition `extract_vacancy` / `extract_resume` с JSON Schema из Pydantic.
- `tool_choice = {"type": "tool", "name": "extract_..."}` — форс-вызов инструмента.
- System prompt (закэширован через `cache_control`) — общие правила: "не выдумывай, оставляй null если данных нет, отвечай на русском в полях с описаниями".
- User prompt: `truncate_by_sentence(raw_text, MAX_EXTRACTOR_CHARS=12000)` — жёсткий cap ~3000 токенов по границе предложения. См. [services/text_utils.py](backend/app/services/text_utils.py) ниже.
- 1 retry при `ToolUseError` / невалидном JSON.
- При повторной неудаче — пишем `extraction_status='failed'`, оставляем пустые JSONB. Документ остаётся в БД, но не участвует в матчинге.

#### Защита от галлюцинаций
- Pydantic-валидация tool_use — Claude не может отдать произвольный текст.
- System prompt запрещает выдумывать факты: "если поле не упомянуто в тексте — ставь null/пустой массив".
- Skills нормализуем lowercase + strip перед сохранением, чтобы JSONB-overlap работал.

### Эмбеддинги через GigaChat (гибридное чанкирование)

#### GigaChat-клиент
```python
from gigachat import GigaChat

class GigaChatEmbedder:
    def __init__(self, credentials: str, model: str = "Embeddings"):
        self._client = GigaChat(credentials=credentials, verify_ssl_certs=False, model=model)

    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        # SDK синхронный → оборачиваем в asyncio.to_thread
        result = await asyncio.to_thread(self._client.embeddings, texts)
        return [item.embedding for item in result.data]
```

- Аутентификация: `GIGACHAT_CREDENTIALS` (base64-строка `client_id:client_secret`) в `.env`. SDK сам обновляет access_token.
- Модель: `Embeddings` (1024d, дефолтная). При плохом качестве можно попробовать `EmbeddingsGigaR`.
- Tenacity-retry: 3 попытки, exponential backoff на 429/5xx.

#### Сборка чанков
После того как Claude отдал structured extraction, формируем **3 текста** для эмбеддинга. Все обрезаются через `truncate_by_sentence` из [text_utils.py](backend/app/services/text_utils.py) — по границе предложения (`. ! ? \n\n`), без обрыва посреди фразы:

| Чанк | Что включаем | Лимит chars | ≈ токенов |
|---|---|---|---|
| **doc** | `raw_text`, truncate | 6000 | 1500 |
| **skills** | `title` + перечисление `hard_skills` + `soft_skills` через запятую | без обрезки (короткий) | 100-300 |
| **experience** | для вакансии: `f"{years_min}-{years_max} лет опыта в: {', '.join(domains)}"`; для резюме: конкатенация `description` всех `positions`, truncate | 3000 | 750 |

Если у Claude `extraction_status='failed'` — кладём в `skills` и `experience` тот же `truncate_by_sentence(raw_text, 3000)` (т.е. три почти-копии — деградация на отказе extractor).

#### Один батч-запрос на документ
Отправляем все 3 текста одним `embeddings([t_doc, t_skills, t_experience])` — GigaChat поддерживает батч. Это 1 API-вызов на документ вместо 3. Экономия квоты × 3.

### Хранение в pgvector

При INSERT строки vacancy/resume сохраняем все 3 вектора в одном UPDATE. Используем `pgvector.sqlalchemy.Vector` тип — он сам сериализует `list[float]` в формат pgvector.

```python
vacancy.embedding_doc = embeddings[0]
vacancy.embedding_skills = embeddings[1]
vacancy.embedding_experience = embeddings[2]
vacancy.extraction_status = "ok"
```

При запросе ближайших — используем оператор `<=>` (cosine distance, 0 = идентично, 2 = противоположно). Похожесть `sim = 1 - distance`.

### 3-этапный матчинг (детально)

#### Общие утилиты — `services/text_utils.py`

```python
import re

_SENT_SPLIT = re.compile(r"(?<=[.!?])\s+|\n{2,}")

def truncate_by_sentence(text: str, max_chars: int) -> str:
    """Обрезает текст по границе предложения, не превышая max_chars."""
    if len(text) <= max_chars:
        return text
    out, used = [], 0
    for sentence in _SENT_SPLIT.split(text):
        chunk = sentence.strip()
        if not chunk:
            continue
        if used + len(chunk) + 1 > max_chars:
            break
        out.append(chunk)
        used += len(chunk) + 1
    return " ".join(out) if out else text[:max_chars]
```

Лимиты-константы (русский ≈4 chars/token):

| Назначение | Лимит chars | ≈ токенов |
|---|---|---|
| `MAX_EXTRACTOR_CHARS` (raw_text для Claude extractor) | 12 000 | 3000 |
| `MAX_EMBED_DOC_CHARS` (GigaChat doc chunk) | 6000 | 1500 |
| `MAX_EMBED_EXP_CHARS` (GigaChat experience chunk) | 3000 | 750 |
| `MAX_SCORER_VAC_CHARS` (vacancy.raw_text в scorer'е) | 8000 | 2000 |
| `MAX_SCORER_RES_CHARS` (resume.raw_text в scorer'е) | 8000 | 2000 |

Все в [config.py](backend/app/core/config.py). Без таких cap'ов один аномально длинный документ (5+ страниц PDF) может удвоить токеновый счёт.

---

#### Этап (1) — Vector pre-filter (pgvector)

##### Запрос

```sql
-- find_candidate_resumes(vacancy_id, owner_id, k=30)
WITH v AS (
  SELECT embedding_doc, embedding_skills, embedding_experience
    FROM vacancies WHERE id = :vacancy_id
)
SELECT r.id,
       1 - (r.embedding_doc        <=> v.embedding_doc)        AS sim_doc,
       1 - (r.embedding_skills     <=> v.embedding_skills)     AS sim_skills,
       1 - (r.embedding_experience <=> v.embedding_experience) AS sim_exp,
       0.4 * (1 - (r.embedding_doc        <=> v.embedding_doc))
     + 0.4 * (1 - (r.embedding_skills     <=> v.embedding_skills))
     + 0.2 * (1 - (r.embedding_experience <=> v.embedding_experience)) AS combined_sim
  FROM resumes r, v
 WHERE r.owner_id = :owner_id
   AND r.extraction_status = 'ok'
 ORDER BY combined_sim DESC
 LIMIT :k_prefilter;
```

##### Параметры и поведение
- `k_prefilter = 30` (config). Цель — отдать ≥ `2 × top_n` чтобы hard-filter этап (2) не оставил пустоту.
- Веса `0.4 / 0.4 / 0.2`: skills и общий смысл документа равноправны, опыт — вспомогательный сигнал.
- `<=>` — cosine distance (0 = идентично, 2 = противоположно). Sim = `1 - distance`.
- HNSW-индекс по `embedding_doc` стабильно работает; section-vectors (skills/experience) на хакатон-объёмах сканируются sequential — это <10 ms на 1000 строк, индексы не нужны.
- Зеркальный запрос `find_candidate_vacancies(resume_id, owner_id, k=30)` для обратного направления (resume → vacancies).

##### Edge cases
- `extraction_status != 'ok'` у целевой вакансии — раз extractor упал, embedder всё равно сохранил 3 одинаковых вектора по `raw_text`, запрос валиден.
- Пустая выдача (нет резюме с `ok`) → API возвращает `{matches: [], note: "no candidates"}`.

---

#### Этап (2) — Hard filter (Python)

[matcher.py](backend/app/services/matcher.py) → `passes_hard_filter`:

```python
def passes_hard_filter(v: Vacancy, r: Resume) -> bool:
    # (a) Локация: если вакансия не remote и не пусто
    if v.location and v.location.lower() not in {"remote", "удалённо", "удаленно"}:
        same_city = (r.location or "").lower() == v.location.lower()
        remote_ok = r.preferred_work_format == "remote"
        if not (same_city or remote_ok):
            return False

    # (b) Формат: вакансия требует офис, кандидат только удалённо
    if v.work_format == "office" and r.preferred_work_format == "remote":
        return False

    # (c) Минимум 1 пересечение по hard_skills (lowercase, strip)
    v_skills = {s["name"].lower().strip() for s in (v.hard_skills or []) if s.get("name")}
    r_skills = {s["name"].lower().strip() for s in (r.hard_skills or []) if s.get("name")}
    if v_skills and not (v_skills & r_skills):
        return False

    return True
```

После фильтра — сортируем по `combined_sim` (из этапа 1, протаскиваем) → берём `TOP_K_LLM = 15` (config). Если прошло меньше — отдаём что есть.

---

#### Этап (3) — LLM scoring (Claude Opus 4.7)

##### Tool schema

```python
class Citation(BaseModel):
    source: Literal["vacancy", "resume"]
    quote: str = Field(max_length=300)

class MatchScore(BaseModel):
    score: int | None = Field(ge=0, le=100)
    explanation: str = Field(max_length=600)
    matching_skills: list[str]
    missing_skills: list[str]
    citations: list[Citation] = Field(min_length=1, max_length=6)

SCORE_TOOL = {
    "name": "score_match",
    "description": "Возвращает оценку соответствия резюме вакансии",
    "input_schema": MatchScore.model_json_schema(),
}
```

##### System prompt — cache block 1 (статичный, hit на всех запросах)

~250 токенов, кэш-хит навсегда после первого вызова:

```
Ты помощник рекрутёра. На вход — одна вакансия и одно резюме кандидата.
Оцени соответствие по шкале 0-100 и обоснуй.

Правила:
- score ≥ 85 означает, что кандидата стоит пригласить на интервью.
- Каждый missing_skill реально отсутствует в резюме (проверь по тексту).
- Каждое утверждение в explanation подкреплено цитатой из citations
  (короткий точный фрагмент из vacancy или resume).
- explanation на русском, 2-4 предложения, без воды и оценочных эпитетов.
- Если данных в резюме недостаточно для уверенной оценки — поставь score=null
  и объясни почему в explanation.
- Всегда вызывай инструмент score_match с результатом, не пиши свободный текст.
```

##### Vacancy block — cache block 2 (общий для всех 15 параллельных вызовов в 1 match-запросе)

~1500-2000 токенов. Cache TTL ephemeral = 5 минут — параллельные вызовы укладываются легко.

```
Вакансия: {title}
Локация: {location | "не указана"}
Формат: {work_format | "не указан"}
Опыт: {years_min}-{years_max | "?"} лет; домены: {domains | "—"}

Обязательные навыки: {[s.name for s in hard_skills if s.required]}
Желательные навыки: {[s.name for s in hard_skills if not s.required]}
Soft skills: {soft_skills}

Полный текст вакансии:
\"\"\"
{truncate_by_sentence(vacancy.raw_text, MAX_SCORER_VAC_CHARS)}
\"\"\"
```

##### Resume block — user message (uncached, разный для каждого вызова)

~1500-2000 токенов. Это единственная часть, которая улетает «полным весом» 15 раз.

```
Резюме кандидата: {candidate_name | "без имени"}
Локация: {resume.location | "не указана"}
Формат: {resume.preferred_work_format | "не указан"}
Общий стаж: {experience.total_years | "?"} лет

Навыки из резюме: {[s.name for s in hard_skills]}
Soft skills: {soft_skills}
Опыт работы: {brief positions list}

Полный текст резюме:
\"\"\"
{truncate_by_sentence(resume.raw_text, MAX_SCORER_RES_CHARS)}
\"\"\"

Оцени соответствие этого кандидата вакансии выше.
```

##### Запрос

```python
async def score_pair(vacancy: Vacancy, resume: Resume) -> MatchScore | MatchError:
    try:
        resp = await claude_client.messages.create(
            model=settings.ANTHROPIC_MODEL,
            max_tokens=600,
            system=[
                {"type": "text", "text": SCORING_INSTRUCTIONS,
                 "cache_control": {"type": "ephemeral"}},        # cache block 1
                {"type": "text", "text": build_vacancy_block(vacancy),
                 "cache_control": {"type": "ephemeral"}},        # cache block 2 — ключ оптимизации
            ],
            tools=[SCORE_TOOL],
            tool_choice={"type": "tool", "name": "score_match"},
            messages=[{"role": "user", "content": build_resume_block(resume)}],
        )
    except (anthropic.APIStatusError, ValidationError) as exc:
        return MatchError(resume_id=resume.id, error=str(exc)[:200])
    tool_use = next(b for b in resp.content if b.type == "tool_use")
    return MatchScore.model_validate(tool_use.input)
```

##### Параллельность и UPSERT

```python
LLM_SEM = asyncio.Semaphore(settings.LLM_CONCURRENCY)  # default 5

async def score_batch(vacancy: Vacancy, resumes: list[Resume]) -> list[MatchScore | MatchError]:
    async def _guarded(r: Resume):
        async with LLM_SEM:
            return await score_pair(vacancy, r)
    return await asyncio.gather(*[_guarded(r) for r in resumes])
```

- Семафор=5: компромисс скорость/rate-limit Anthropic.
- Все 15 вызовов отправляются практически одновременно, cache block 2 для vacancy записывается первым освободившимся → остальные 14 hit на чтении.
- Tenacity на 429/5xx внутри `score_pair`: 3 попытки, exponential backoff.

После `gather`:
```python
for resume, result in zip(top_k, results):
    db.execute(
        insert(Match)
          .values(vacancy_id=v.id, resume_id=resume.id,
                  score=result.score if isinstance(result, MatchScore) else None,
                  explanation=result.explanation if isinstance(result, MatchScore) else None,
                  matching_skills=result.matching_skills if ... else [],
                  missing_skills=result.missing_skills if ... else [],
                  error=result.error if isinstance(result, MatchError) else None,
                  computed_at=func.now())
          .on_conflict_do_update(
             index_elements=["vacancy_id", "resume_id"],
             set_={"score": ..., "explanation": ..., "computed_at": func.now()})
    )
await db.commit()
```

##### Финальный фильтр

```python
final = [m for m in matches if m.score is not None and m.score >= settings.MATCH_SCORE_THRESHOLD]
final.sort(key=lambda m: m.score, reverse=True)
return final[:top_n]
```

---

#### Слой кэша — таблица `matches`

При входе в match-эндпоинт:
1. SELECT (resume_id, score, computed_at, ...) FROM matches WHERE vacancy_id=:v AND resume_id IN (top_30_from_prefilter).
2. **Не кэшированные** (нет строки) пары — кладём в очередь на скоринг. Кэшированные — берём как есть.
3. Запускаем `score_batch` только на не-кэшированных.
4. Объединяем cached + freshly_scored, фильтруем по threshold, сортируем, возвращаем top_n.

Так повторный `GET /api/matches/vacancy/1` после первого вызова не делает **ни одного** LLM-вызова — только SELECT.

##### Когда инвалидировать
- MVP: никогда. Документы не редактируются.
- При DELETE vacancy/resume — каскад `ON DELETE CASCADE` уже зачищает matches.

---

#### Token-cost (1 match-запрос, top_n=10, top_k=15 для скоринга)

| Блок | Tokens | Cache state | Effective input tokens |
|---|---|---|---|
| System instructions (block 1) | 250 | write 1× (×1.25), read 14× (×0.1) | 250×1.25 + 250×0.1×14 = **663** |
| Vacancy (block 2) | 1800 | write 1× (×1.25), read 14× (×0.1) | 1800×1.25 + 1800×0.1×14 = **4 770** |
| Resume (user) — 15× | 1800 × 15 | uncached | **27 000** |
| **Σ input-eq** |  |  | **~32 400** |
| Output (до 600 × 15) | 350 × 15 | n/a | **5 250** (×5 cost-factor для Opus) |

При прайсинге Opus 4.7 (≈$15/Mtok input, $75/Mtok output):
- **С vacancy-cache (план)**: $0.49 input + $0.39 output ≈ **$0.88 за match-request**
- **Без vacancy-cache (наивный план)**: $0.97 + $0.39 ≈ **$1.36**
- **Экономия ≈ 35%** на каждый «холодный» match. Повторы — из `matches`-кэша, $0.

Демо-сценарий: 5 вакансий × 1 первый match = ~$4.4. Дальнейшие показы — бесплатно.

### Формула релевантности

Финальный user-facing скор = **LLM score**. Это единственное число, которое видит рекрутёр. Векторная похожесть и skill-overlap — внутренние сигналы для префильтра, в API не выставляются (только в debug-эндпоинт, если решим добавить).

Порог `≥ 85` — из критерия хакатона. Пример отрисовки для рекрутёра в UI:

```
Score: 92/100  ✓ Выше порога 85

Совпадения: Python, Django, PostgreSQL, REST API
Не хватает: опыт с Kubernetes (1 год требуется, в резюме не указано)

Обоснование: Кандидат имеет 6 лет коммерческого опыта Python-разработки в e-commerce
(цитата: «6 лет в e-commerce, последние 4 — техлид»), что превышает требование 5+ лет.
Все ключевые хард-скиллы подтверждены конкретными проектами. Из требуемых отсутствует
только опыт с Kubernetes — в резюме упомянут Docker, но не оркестрация.
```

### Изменения в существующих upload-эндпоинтах

POST `/api/vacancies` и POST `/api/resumes` теперь после парсинга:
1. Сохраняют черновик с `extraction_status='pending'`, `raw_text` заполнен.
2. **Синхронно** вызывают extractor + embedder (для хакатона async-worker избыточен).
3. UPDATE строки с JSONB + векторами + `status='ok'` (или `'failed'` при ошибке).
4. Возвращают полный объект.

Если extractor/embedder упал — 201 всё равно отдаём, в ответе видно `extraction_status='failed'` и UI это показывает.

### Обработка ошибок и отказы

| Сценарий | Поведение |
|---|---|
| GigaChat 429/timeout | Tenacity 3 retry → `extraction_status='failed'`, raw_text сохранён, 201 OK |
| Claude extractor 5xx | То же |
| Claude scorer 5xx на отдельной паре | `error="scoring_failed"` для этой пары, остальные продолжают |
| `pgvector` запрос на документе без эмбеддингов | `WHERE extraction_status='ok'` отфильтровывает их |
| Пустой top-30 после vector pre-filter | API возвращает `[]` + поле `note: "no candidates above threshold"` |
| Битый PDF | 422 из парсера (Stage 1 уже работает) |

Никаких голых 500-ок. Глобальный handler из Этапа 1 ловит остаток.

### Производительность и кэширование

#### Профиль latency (целевой)
- Upload файла: parser ≤200ms + Claude extractor ~3-5s + GigaChat batch ~500ms = **~4-6s**. Приемлемо для UI с loading state.
- Match request (свежий, top-N=10):
  - Vector pre-filter: ~30ms (HNSW на ≤1000 строк)
  - Hard filter: ~5ms
  - Claude scoring 10 параллельных пар: ~3-5s
  - Total: **~5s**
- Match request (cached): SQL без LLM, **~50ms**.

#### Стратегии кэширования (3 уровня)
1. **`matches` таблица** — главный кэш скоринга. Повтор match-запроса = 0 LLM-вызовов.
2. **Эмбеддинги** в `embedding_*` колонках — вычисляются 1 раз на upload, переживают всё.
3. **Claude prompt cache** (два cache breakpoints через `cache_control: ephemeral`):
   - Block 1 = scoring instructions (~250 tok). Кэш-хит на каждом match-запросе после первого ever.
   - Block 2 = vacancy content (~1800 tok). Кэш-хит на 14 из 15 параллельных вызовов внутри одного match-запроса. Экономия **~35%** input-токенов на каждом «холодном» матче (подробный расчёт в секции [Token-cost](#token-cost-1-match-запрос-top_n10-top_k15-для-скоринга) выше).

#### Когда инвалидировать кэш матчей
- Хакатон-MVP: **никогда** (документы не редактируются).
- На будущее: при `PATCH /api/vacancies/{id}` или удалении — `DELETE FROM matches WHERE vacancy_id = ...`.

### Файлы для создания/изменения (Этап 2)

| Файл | Действие | Зачем |
|---|---|---|
| [docker-compose.yml](docker-compose.yml) | edit | образ `pgvector/pgvector:pg16` |
| [backend/pyproject.toml](backend/pyproject.toml) | edit | + `pgvector`, `gigachat` |
| [.env.example](.env.example) | edit | + `GIGACHAT_CREDENTIALS`, `GIGACHAT_SCOPE`, `GIGACHAT_MODEL`, `MATCH_SCORE_THRESHOLD=85` |
| [backend/app/core/config.py](backend/app/core/config.py) | edit | + GigaChat и matching settings |
| [backend/app/db/models.py](backend/app/db/models.py) | edit | + 3 vector колонки + `extraction_status` |
| `backend/alembic/versions/20260516_0002_add_vector_columns.py` | new | extension + колонки + HNSW-индексы |
| [backend/app/services/text_utils.py](backend/app/services/text_utils.py) | new | `truncate_by_sentence` + лимит-константы (общая утилита для extractor/embedder/scorer) |
| [backend/app/services/claude.py](backend/app/services/claude.py) | new | Anthropic-клиент + cache_control + retry |
| [backend/app/services/extractor.py](backend/app/services/extractor.py) | new | tool_use → Pydantic-схемы |
| [backend/app/services/embedder.py](backend/app/services/embedder.py) | new | GigaChat client + batch embeddings |
| [backend/app/services/repository.py](backend/app/services/repository.py) | new | pgvector-запросы (find_candidate_resumes / vacancies / orphan-агрегации) |
| [backend/app/services/matcher.py](backend/app/services/matcher.py) | new | 3-этапный pipeline, asyncio.gather с семафором, UPSERT в matches |
| [backend/app/api/vacancies.py](backend/app/api/vacancies.py) | edit | в upload вызов extractor+embedder; в response `extraction_status` |
| [backend/app/api/resumes.py](backend/app/api/resumes.py) | edit | то же |
| [backend/app/api/matches.py](backend/app/api/matches.py) | new | 4 эндпоинта матчей (+ опц. recompute) |
| [backend/app/schemas/matches.py](backend/app/schemas/matches.py) | new | Pydantic-схемы ответа |
| [backend/app/schemas/vacancies.py](backend/app/schemas/vacancies.py) | edit | + `extraction_status` |
| [backend/app/schemas/resumes.py](backend/app/schemas/resumes.py) | edit | + `extraction_status` |
| [backend/app/main.py](backend/app/main.py) | edit | include_router(matches_api) |
| [backend/app/cli.py](backend/app/cli.py) | new | Typer: ingest-vacancy, ingest-resume, match-vacancy, match-resume, demo |
| [scripts/export_openapi.py](scripts/export_openapi.py) | run | регенерация openapi.json/yaml после изменений |

### План коммитов Этапа 2

| # | Сообщение | Что входит |
|---|---|---|
| 1 | `chore: switch postgres image to pgvector and add deps` | docker-compose.yml, pyproject.toml (+pgvector, +gigachat), .env.example |
| 2 | `feat: add vector columns and extraction status` | models.py + миграция 0002 + индексы HNSW |
| 3 | `feat: text truncation utility` | services/text_utils.py + лимит-константы в config |
| 4 | `feat: gigachat embeddings client` | services/embedder.py |
| 5 | `feat: anthropic client with cache control and retries` | services/claude.py (поддержка multi-block system + cache_control) |
| 6 | `feat: claude extractor with tool use` | services/extractor.py + Pydantic-схемы |
| 7 | `feat: integrate extraction and embeddings into upload` | api/vacancies.py, api/resumes.py edits, schemas с extraction_status |
| 8 | `feat: pgvector repository queries` | services/repository.py |
| 9 | `feat: claude matcher with cached vacancy block and parallel scoring` | services/matcher.py + 2-block cache_control + matches UPSERT |
| 10 | `feat: match endpoints with four flows` | api/matches.py, schemas/matches.py, main.py include |
| 11 | `feat: typer cli with demo command` | app/cli.py |
| 12 | `chore: regenerate openapi spec` | openapi.json/yaml |

Каждый коммит — автор `chiaker`, без `Co-Authored-By: Claude`, стиль строчный.

### Верификация end-to-end (Этап 2)

1. **Сборка**: `docker compose up --build` → `db (healthy)` (pgvector extension создаётся миграцией) и `backend` слушает 8000.
2. **Регистрация + login** через Swagger (как в Этапе 1).
3. **Загрузка 1 вакансии и 5 резюме**:
   - В response каждого — `extraction_status: "ok"`, в `hard_skills` ровно те, что в исходном файле.
   - Проверить в БД: `SELECT id, extraction_status, octet_length(embedding_doc::text) FROM vacancies;` — embedding_doc не NULL, ~6000+ байт (1024 floats).
4. **Match-запрос**: `GET /api/matches/vacancy/1?top=5`:
   - Возвращает массив с `score ≥ 85`.
   - Каждый объект: `{resume_id, score, explanation, matching_skills, missing_skills, citations}`.
   - `explanation` — на русском, 2-4 предложения, без галлюцинаций (проверить по `citations`).
5. **Кэширование**: повторный запрос того же → существенно быстрее (нет LLM-вызовов, только SELECT из matches).
6. **Orphan**: загрузить заведомо нерелевантное резюме (например, повар на вакансию Python-разработчика) → `GET /api/matches/orphan-resumes?top=5` возвращает этого кандидата.
7. **Качество**: на 10 размеченных парах (5 релевантных, 5 нет) посчитать долю корректных вердиктов ≥85% → цель **≥80%** для максимума баллов критерия 9.
8. **Негатив (no-500)**:
   - Невалидный `GIGACHAT_CREDENTIALS` → 503 при upload, не 500.
   - Anthropic 401 → 503.
   - Загрузка резюме на абракадабре → `extraction_status='failed'`, в матчинге не участвует.
9. **CLI**: `docker compose exec backend python -m app.cli demo` — прогоняет весь flow на семплах.
10. **OpenAPI**: `python scripts/export_openapi.py` → в спеке появились `/api/matches/*` и схемы матчей.

### Что НЕ делаем на Этапе 2 (откладываем)

- **Фронтенд** целиком — Этап 3. Бэкенд тестируется через Swagger и Postman.
- **Демо-семплы** (vacancies/resumes на русском) — Этап 3, QA-роль.
- **Background-воркер для извлечения/эмбеддингов** (Celery/RQ) — пока синхронно. Если upload станет тормозить >10s — поднимем на Этапе 3.
- **Pytest+httpx тесты** — точечно, если останется время; для хакатона ручной верификации через Swagger достаточно.
- **Edit-эндпоинты** для вакансий/резюме (PATCH) — out of scope.
- **Re-ranking моделями** (cross-encoder) — overkill для хакатона; LLM-скоринг покрывает.
- **OCR для сканированных PDF** — отдельный этап если жюри попросит.

### Открытые риски Этапа 2

1. **Квота GigaChat**: free-tier ограничен по токенам. Для демо (1 вак × 20 рез = 20 doc-эмбеддингов × 3 чанка = 60 запросов) хватит, но при массовой загрузке упрёмся. Mitigation: лимит размера `raw_text` до 5000 символов в embedder (truncate); кэш эмбеддингов в БД.
2. **GigaChat SSL**: SDK требует `verify_ssl_certs=False` на некоторых сетях (корпоративные CA). Документируем в README.
3. **HNSW recall**: с дефолтными параметрами (`m=16, ef_construction=64`) recall ~95% на хакатон-объёмах. Если top-30 не покрывает истинно лучших — поднимем `ef_search`. Не критично, потому что LLM в шаге 3 всё равно фильтрует.
4. **Длинный raw_text упирается в context window GigaChat**: модель `Embeddings` имеет лимит. Mitigation: truncate `embedding_doc`-чанка до ~1500 токенов перед запросом.
5. **Anthropic токены**: 10 параллельных Claude-вызовов на match-запрос × ~2K input токенов × top=10 кандидатов = ~20K input + ~3K output. Cache_control на system prompt снижает стоимость до ~10% после первого запроса.
6. **Несоответствие словарей**: Claude нормализует skills как "Python", но в резюме может быть "питон". Mitigation: extractor имеет инструкцию приводить к каноническому английскому названию + lowercase сравнение в hard-filter.

### Зависимости между ролями (5 человек, см. распределение из чата)

- **Backend Lead / Infra (#1)** — миграция pgvector в compose, exception handlers для новых сервисов.
- **Auth & Data (#2)** — миграция 0002, репозиторий с pgvector-запросами.
- **AI/ML (#3)** — embedder, extractor, matcher, system prompts.
- **Frontend (#4)** — ждёт API контракты до конца Этапа 2 (~середина дня 2).
- **QA / Demo / Docs (#5)** — параллельно собирает 5 вакансий + 20 резюме; готовит размеченную пару из 10 для оценки качества.
