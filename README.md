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
- `OPENAI_API_KEY`: Required when using the OpenAI generator.
- `GEMINI_API_KEY` or `GOOGLE_API_KEY`: Required when using the Gemini generator.
- `LLM_PROVIDER`: Optional default provider for the generator script. Use `openai` or `gemini`.
- `LLM_MODEL`: Optional model override for the generator script.
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
- `GET /api/questions` - flat question list with optional `topic`, `subtopic`, `limit`, and `offset`
- `GET /api/topics/{topic}/subtopics` - list subtopics of a topic with question counts
- `GET /api/topics/{topic}/subtopics/{subtopic}/questions` - practice questions for one subtopic (`limit`, `offset`)
- `GET /api/topics/{topic}/questions` - list questions for a topic grouped by subtopic
- `GET /api/questions/{question_id}` - fetch one question by id
- `POST /api/questions/bulk` - bulk insert a generated question batch
- `PATCH /api/questions/{question_id}` - partial question update
- `DELETE /api/questions/{question_id}` - delete one question
- `PUT /api/topics/{topic}/rename` - rename a topic across all questions
- `PUT /api/topics/{topic}/subtopics/{subtopic}/rename` - rename a subtopic across all matching questions

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

Generate and seed questions directly into MongoDB:

```bash
python generator/batch_generator.py --topic "Python Basics" --count 10 --provider openai
```

To use Gemini instead:

```bash
python generator/batch_generator.py --topic "Python Basics" --count 10 --provider gemini
```

## Docker

Build and run the container:

```bash
docker build -t mcq-backend .
docker run -p 8000:8000 -e MONGO_URL="mongodb://host.docker.internal:27017/mcq_db" mcq-backend
```

The container listens on port `8000` and starts Uvicorn with the FastAPI app.