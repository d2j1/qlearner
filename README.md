# MCQ Practice Backend

Production-ready FastAPI backend for an interactive MCQ practice application.

## Stack

- Python 3.11+
- FastAPI
- Beanie ODM with Motor / AsyncIOMotorClient
- Pydantic v2
- Uvicorn
- MongoDB

## Run Locally

1. Start MongoDB and ensure it is reachable at `mongodb://localhost:27017/mcq_db`.
2. Create and activate a virtual environment.
3. Install dependencies:

```bash
pip install -r requirements.txt
```

4. Start the API:

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

## Environment Variables

- `MONGO_URL`: MongoDB connection string. Defaults to `mongodb://localhost:27017/mcq_db`.
- `CORS_ALLOW_ORIGINS`: Comma-separated list of allowed frontend origins.
- `CORS_ALLOW_CREDENTIALS`: Set to `true` if cross-site credentials are required.
- `GEMINI_API_KEY`: Gemini API key (free at aistudio.google.com); used by the default LLM config and the generator.
- `LLM_MODEL`, `LLM_BASE_URL`, `LLM_API_KEY_ENV`: Optional generator script overrides.
- `JWT_SECRET`: Secret used to sign login tokens. Set a long random value in production.
- `JWT_EXPIRE_MINUTES`: Token lifetime. Defaults to 7 days.
- `ADMIN_EMAILS`: Comma-separated emails that get the `admin` role on register/login.

## API

### Auth

Send `Authorization: Bearer <access_token>` on protected routes. Reads are public; every write (bulk, PATCH, DELETE, renames) requires an admin (401 without a token, 403 for non-admins).

- `POST /api/auth/register` - `{ email, name, password }` (password 8-72 chars) -> `{ access_token, token_type, expires_in, user }` (409 if the email exists)
- `POST /api/auth/login` - `{ email, password }` -> same shape as register (401 on bad credentials)
- `GET /api/auth/me` - current user `{ id, email, name, role, created_at }`

- `GET /health` - liveness check
- `GET /ready` - MongoDB readiness check
- `GET /api/topics` - list available topics
- `GET /api/questions` - flat question list with optional `topic`, `subtopic`, `q` (case-insensitive search in question text), `limit`, and `offset`
- `GET /api/topics/{topic}/subtopics` - list subtopics of a topic with question counts
- `GET /api/topics/{topic}/subtopics/{subtopic}/questions` - practice questions for one subtopic (`limit`, `offset`)
- `GET /api/topics/{topic}/questions` - list questions for a topic grouped by subtopic
- `GET /api/questions/{question_id}` - fetch one question by id
- `POST /api/questions/bulk` - bulk insert a generated question batch
- `PATCH /api/questions/{question_id}` - partial question update
- `DELETE /api/questions/{question_id}` - delete one question
- `GET /api/taxonomy` - admin: every topic and subtopic used by questions (including drafts) or notes, with `question_count`, `draft_count` and `note_count`; feeds rename dropdowns
- `PUT /api/topics/{topic}/rename` `{ new_topic }` - admin: rename a topic on every question, note and generation job -> `{ modified_count, notes_modified, jobs_modified, merged }` (404 unknown topic, 422 empty or unchanged name; `merged` = the new name already existed)
- `PUT /api/topics/{topic}/subtopics/{subtopic}/rename` `{ new_subtopic }` - admin: same, for one subtopic within a topic

### Question shape

Frontend payloads and responses use:

- `topic: string`
- `subtopic: string`
- `question_text: string`
- `options: [{ index, text }]`
- `correct_option_indices: number[]`
- `explanation: string`
- `correct_option_indices` must be non-empty, have no duplicates, and each value must match an option `index` (422 otherwise)
- `difficulty: "EASY" | "MEDIUM" | "HARD"` (defaults to `MEDIUM`)

## LLM Batch Generator

Generate and seed questions directly into MongoDB. It uses Gemini's free tier by default (set `GEMINI_API_KEY`):

```bash
python generator/batch_generator.py --topic "Python Basics" --count 10
```

Any OpenAI-compatible API works by overriding the model, base URL and key variable:

```bash
python generator/batch_generator.py --topic "Python Basics" --model llama-3.3-70b-versatile   --base-url https://api.groq.com/openai/v1 --api-key-env GROQ_API_KEY
```

### LLM configs (admin API)

Models the app can generate with are stored in the `llm_configs` collection; a "Gemini Flash (free)" config (model `gemini-flash-latest`) is seeded on first start. Each config stores only the *name* of the env var holding its key.

- `GET /api/llm-configs` - list configs (`api_key_set` shows whether the key env var is present)
- `POST /api/llm-configs` - `{ name, base_url, model, api_key_env, is_free, enabled, is_default }`
- `PATCH /api/llm-configs/{id}` / `DELETE /api/llm-configs/{id}`
- `POST /api/llm-configs/{id}/test` - optional `{ prompt }`; returns `{ ok, latency_ms, output, input_tokens, output_tokens, error }`

### Notes, prompts and AI generation (admin API)

Generated questions are saved as **drafts** and stay out of practice until approved. Questions without a `status` (created before this feature) count as approved.

- Notes: `GET/POST /api/notes` (filter `topic`, `subtopic`), `GET/PATCH/DELETE /api/notes/{id}`
- Prompt templates (immutable, versioned; posting an existing `name` creates its next version): `GET /api/prompts` (`all_versions=true` for history), `GET /api/prompts/{id}`, `POST /api/prompts`, `POST /api/prompts/{id}/default`, `GET /api/prompts/placeholders`
- Jobs: `POST /api/generation/jobs` `{ topic, subtopic, note_ids?, focus?, extra_instructions?, count (1-50), difficulty (MIXED|EASY|MEDIUM|HARD), allow_outside_knowledge?, llm_config_id?, prompt_template_id? }` -> 202 job; poll `GET /api/generation/jobs/{id}` until `succeeded` or `failed`; `GET /api/generation/jobs?status=`
- Drafts: `GET /api/questions/drafts?job_id=&topic=&subtopic=`, `POST /api/questions/{id}/approve|reject|regenerate`, bulk `POST /api/questions/approve|reject` `{ ids }`; edit with `PATCH /api/questions/{id}`

Jobs run in the API process. Long notes are split into ~12k-character chunks, near-duplicate questions in the same subtopic are skipped, and jobs interrupted by a restart are marked failed on the next start.

## Deployment

The API is hosted on [Render](https://render.com) as a Docker web service built from this repo's `Dockerfile`.

| Item | Value |
| --- | --- |
| Live URL | https://qlearner.onrender.com |
| API docs | https://qlearner.onrender.com/docs |
| Health / readiness | `/health`, `/ready` |
| Render service | `qlearner` (ID `srv-d9mrclrm8hqs73cvjbig`), environment `Production` |
| Source | GitHub `d2j1/qlearner`, branch `main` |
| Instance | Free tier |
| Deploys | Manual: Render dashboard -> **Manual Deploy** -> *Deploy latest commit* |

Notes:

- Pushing to `main` does **not** deploy. Trigger a manual deploy after merging.
- The free instance spins down when idle; the first request after that can take 50+ seconds.
- Set `MONGO_URL`, `JWT_SECRET`, `ADMIN_EMAILS` and `CORS_ALLOW_ORIGINS` (include the frontend's URL) under the service's **Environment** settings. The local `.env` is not deployed.

## Docker

Build and run the container:

```bash
docker build -t mcq-backend .
docker run -p 8000:8000 -e MONGO_URL="mongodb://host.docker.internal:27017/mcq_db" mcq-backend
```

The container listens on port `8000` and starts Uvicorn with the FastAPI app.