# Refinery Notification Intelligence Assistant (Backend)

## Overview

This repository implements the **backend** for the *Refinery Notification Intelligence Assistant* – a FastAPI service that enables users to upload SAP PM notification data, run deterministic analytics, and ask natural‑language questions powered by LLMs (Gemini or OpenAI).  The backend does **not** perform any calculation itself; instead it normalises the uploaded data, runs a fast analytics engine, and then uses an LLM only for intent classification and response generation.
> **Security note:** No API keys are hard‑coded in the source code or documentation. Keys must be supplied via the `.env` file or environment variables.

## What the Project Does

1. **File Upload** – Users POST an Excel or CSV file containing maintenance notifications.
2. **Schema Normalisation** – The raw file is parsed and normalised into a clean Pydantic model.
3. **Analytics Engine** – Lightweight pandas‑based functions compute summary statistics, counts, overdue items, etc.
4. **AI Intent Layer** – An LLM classifies the user’s natural‑language query and maps it to one of the analytics functions.
5. **Response Generation** – The selected analytics function is executed and the result is wrapped in a friendly JSON response.

The service is deliberately split into **deterministic** (analytics) and **generative** (LLM) stages so that calculations are reproducible and cost‑effective.

## Architecture Flow

```
Upload → Schema Normalisation → Analytics Engine → AI Intent → Response Generator → JSON API
```

- **Upload** (router `upload.py`)
- **Chat** (router `chat.py` – handles the LLM‑driven conversation)
- **Services**
  - `file_parser.py` – reads Excel/CSV.
  - `schema_normalizer.py` – validates and normalises data.
  - `analytics_engine.py` – deterministic pandas calculations.
  - `ai_intent.py` – LLM classification (Gemini or OpenAI).
  - `response_generator.py` – builds the final response.
   
## Technology Stack & Libraries

- **Core Framework**: FastAPI – high‑performance async API framework.
- **ASGI Server**: uvicorn – runs the FastAPI app locally.
- **Data Handling**: pandas – used for deterministic analytics and summarisation.
- **Schema Validation**: pydantic & pydantic‑settings – type‑safe request/response models and environment configuration.
- **LLM Providers**:
  - **Google Gemini** – via `google‑genai` library.
  - **OpenAI** – via `openai` library.
- **HTTP Client**: httpx (pinned < 0.28.0 for OpenAI compatibility).
- **File Parsing**: python‑multipart for handling uploads; openpyxl & xlrd for Excel support.
- **Environment Management**: python‑dotenv – loads `.env` variables.
- **Utilities**: logging – standardized logs for debugging and monitoring.


## Setup & Run Locally

### Prerequisites
- Python **3.10+** (the project was tested with 3.10/3.11).
- Git.
- (Optional) Docker if you prefer containerised execution.

### 1. Clone the Repository
```bash
git clone https://github.com/your‑org/bpcl_notification_be.git
cd bpcl_notification_be
```

### 2. Create a Virtual Environment
```bash
python3 -m venv venv
source venv/bin/activate
```

### 3. Install Dependencies
```bash
pip install --upgrade pip
pip install -r requirements.txt
```
> **Note:** `requirements.txt` pins `httpx<0.28.0` to stay compatible with the `openai` client.

### 4. Configure Environment Variables
Copy the example file and fill in the required keys:
```bash
cp .env.example .env
# Edit .env
#   GEMINI_API_KEY=your‑gemini‑key
#   OPENAI_API_KEY=your‑openai‑key
#   AI_PROVIDER=gemini   # or "openai"
```

### 5. Run the FastAPI Server
```bash
uvicorn app.main:app --reload
```
The API will be available at `http://127.0.0.1:8000`.

### 6. Explore the Documentation
- Swagger UI: `http://127.0.0.1:8000/docs`
- ReDoc: `http://127.0.0.1:8000/redoc`

## Primary Endpoints
| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/upload` | Upload an Excel/CSV file containing notifications.
| `POST` | `/api/chat`   | Send a natural‑language query; the backend classifies intent and returns analytics results.
| `GET`  | `/api/health` | Simple health‑check endpoint.

## Running Tests (Optional)
If you add unit tests later, you can run them with:
```bash
pytest
```

## Contributing
1. Fork the repository.
2. Create a feature branch (`git checkout -b feature/your‑feature`).
3. Ensure code follows the existing style (type‑hints, Pydantic models, docstrings).
4. Submit a Pull Request.

## License
This project is licensed under the **MIT License** – see `LICENSE` for details.

---
*Feel free to open issues for bugs or feature requests. Happy coding!*
