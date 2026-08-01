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

## API

- `GET /health` - liveness check
- `GET /ready` - MongoDB readiness check
- `GET /api/topics` - list available topics
- `GET /api/questions` - flat question list with optional `topic`, `subtopic`, `limit`, and `offset`
- `GET /api/topics/{topic}/questions` - list questions for a topic grouped by subtopic
- `GET /api/questions/{question_id}` - fetch one question by id
- `POST /api/questions/bulk` - bulk insert a generated question batch
- `PATCH /api/questions/{question_id}` - partial question update
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