# Xrary: Automated SDE Hiring Signal Agent

**Xrary** is an automated agent that searches X (Twitter) for Software Development Engineer (SDE) internship hiring posts, intelligently judges them using OpenAI's GPT-4o-mini, filters out duplicates, and sends real-time WhatsApp alerts via Twilio.

---

## 🎯 Features

- **X (Twitter) Search**: Reverse-engineered GraphQL client to search tweets without official API limits
- **Intelligent Filtering**: Two-stage filtering system:
  - **Cheap Filter**: Fast keyword-based pre-filtering (hiring, internship, apply now, etc.)
  - **Smart Filter**: LLM-powered classification with confidence scoring
- **Duplicate Detection**: SQLite-backed deduplication to avoid alert spam
- **WhatsApp Alerts**: Sends formatted hiring notifications via Twilio
- **Scheduled Polling**: Configurable interval-based polling (default: 10 minutes)
- **Comprehensive Logging**: JSON-structured logs with ISO timestamps (stdout + rotating file)
- **Production-Ready**: Graceful shutdown, error handling, containerized deployment

---

## 🏗️ Architecture

### System Overview

```
┌─────────────────────────────────────────────────────────────┐
│                    Xrary Hiring Agent                        │
├─────────────────────────────────────────────────────────────┤
│  APScheduler (Background Task Scheduler)                     │
│  └─ Runs agent cycle every N minutes                         │
├─────────────────────────────────────────────────────────────┤
│  LangGraph Workflow (5-Node Pipeline)                        │
│  ├─ [Search Node]   → XReverseClient (GraphQL search)        │
│  ├─ [Filter Node]   → Cheap keyword filter + dedup           │
│  ├─ [Judge Node]    → LLMClient (GPT-4o-mini classification) │
│  ├─ [Notify Node]   → WhatsAppClient (Twilio)                │
│  └─ [Sleep Node]    → Record last_run timestamp              │
├─────────────────────────────────────────────────────────────┤
│  Data Layer                                                  │
│  ├─ SQLAlchemy ORM (SeenTweet, AgentState models)            │
│  ├─ SQLite Database (data/hiring_agent.db)                   │
│  └─ LangGraph Checkpoint (data/hiring_agent_graph.sqlite)    │
├─────────────────────────────────────────────────────────────┤
│  External APIs                                               │
│  ├─ X (Twitter) GraphQL SearchTimeline endpoint              │
│  ├─ OpenAI API (GPT-4o-mini, structured output)              │
│  └─ Twilio WhatsApp API                                      │
└─────────────────────────────────────────────────────────────┘
```

### LangGraph Pipeline (5-Node DAG)

```
START
  ↓
[SEARCH] → Fetch tweets matching query
  ↓
[FILTER] → Keyword-based filtering + deduplication
  ↓
[JUDGE] → LLM classification (is_hiring? confidence > 0.7?)
  ↓
[NOTIFY] → Send WhatsApp alerts + mark seen
  ↓
[SLEEP] → Record timestamp for next cycle
  ↓
END
```

**Error Handling**: Each node catches exceptions, logs errors, increments error counter, and continues (no crash).

### Key Components

#### 1. **XReverseClient** (`src/clients/x_reverse_client.py`)
- Async GraphQL client for X/Twitter search
- Reverse-engineered SearchTimeline endpoint
- Nested response parsing (data → search_by_raw_query → timeline → entries → tweets)
- Built-in retry logic (3 attempts, exponential backoff)
- Error classes: `XRateLimitError`, `XAuthError`, `XGraphQLError`

#### 2. **LLMClient** (`src/clients/llm_client.py`)
- Async OpenAI client using GPT-4o-mini
- Structured output parsing with Pydantic validation
- JudgeResult model: `is_hiring`, `confidence [0-1]`, `company`, `role`, `location`, `apply_link`
- **Confidence override**: If confidence < 0.7, forces `is_hiring=False` (conservative)
- Graceful fallback to JSON mode if structured output unavailable

#### 3. **WhatsAppClient** (`src/clients/whatsapp_client.py`)
- Twilio WhatsApp integration
- Message formatting with WhatsApp markdown (*bold*, _italic_)
- Returns message SID for tracking

#### 4. **Tweet Filtering** (`src/services/tweet_filter.py`)
- `cheap_filter(tweet) → bool` function
- Keywords: HIRING_KEYWORDS, INTERN_KEYWORDS, SPAM_KEYWORDS
- Rules:
  - Text length > 20 chars
  - Must contain hiring OR intern keyword
  - No spam keywords (crypto, nft, airdrop, etc.)
  - Not a retweet
  - Author handle not spam-tagged

#### 5. **Deduplicator** (`src/services/deduplicator.py`)
- SQLAlchemy-backed deduplication
- `is_seen(tweet_id)` → bool
- `mark_seen(tweet, judge_result, notified)` → persists to DB

#### 6. **Message Formatter** (`src/services/message_formatter.py`)
- `format_hiring_alert(tweet, judge_result)` → WhatsApp markdown string
- 400-char truncation with metadata (company, role, location, confidence, timestamp)

#### 7. **Configuration** (`src/config.py`)
- Pydantic Settings loading from `.env`
- Required fields: OpenAI API key, Twilio credentials, X auth cookies, etc.
- Validation: WhatsApp numbers must start with "whatsapp:" prefix

#### 8. **Database** (`src/storage/`)
- SQLAlchemy ORM with SQLite backend
- **Models**:
  - `SeenTweet`: tweet_id (unique), text, author_handle, detected_at, notified, confidence_score, company, role
  - `AgentState`: last_run, notifications_sent, error_count, updated_at

#### 9. **Logging** (`src/utils/logging_config.py`)
- Structlog JSON output to stdout
- Rotating file handler to `logs/hiring_agent.log` (10MB max, 5 backups)
- ISO timestamps, context binding

#### 10. **Retry Decorator** (`src/utils/retry.py`)
- Tenacity-based retry with exponential backoff
- Retries on: `httpx.HTTPStatusError`, `httpx.ConnectError`, `TimeoutError`
- 3 attempts, 2-30 second backoff range

#### 11. **Rate Limiter** (`src/utils/rate_limiter.py`)
- Thread-safe fixed-window rate limiter
- `RateLimiter(max_requests, window_seconds)`
- `acquire() → bool` and `wait_time() → float`

---

## 📁 Folder Structure

```
Xrary/
├── src/                          # Main source code
│   ├── __init__.py
│   ├── config.py                 # Pydantic Settings (env loading)
│   ├── main.py                   # Entry point (APScheduler, signal handling)
│   ├── agents/
│   │   ├── __init__.py
│   │   ├── hiring_agent.py       # LangGraph pipeline orchestration
│   │   └── nodes/
│   │       ├── __init__.py
│   │       ├── search_node.py    # Search tweets
│   │       ├── filter_node.py    # Cheap filter + dedup
│   │       ├── judge_node.py     # LLM classification
│   │       └── notify_node.py    # WhatsApp alerts
│   ├── clients/
│   │   ├── __init__.py
│   │   ├── x_reverse_client.py   # X GraphQL client
│   │   ├── llm_client.py         # OpenAI GPT-4o-mini client
│   │   └── whatsapp_client.py    # Twilio WhatsApp client
│   ├── services/
│   │   ├── __init__.py
│   │   ├── tweet_filter.py       # Cheap keyword filtering
│   │   ├── deduplicator.py       # SQLAlchemy-backed dedup
│   │   └── message_formatter.py  # WhatsApp message formatting
│   ├── storage/
│   │   ├── __init__.py
│   │   ├── database.py           # SQLAlchemy engine, session factory
│   │   ├── models.py             # ORM models (SeenTweet, AgentState)
│   │   └── migrations/           # Alembic migrations (future)
│   └── utils/
│       ├── __init__.py
│       ├── logging_config.py     # Structlog configuration
│       ├── retry.py              # Tenacity retry decorator
│       └── rate_limiter.py       # Thread-safe rate limiter
│
├── scripts/
│   ├── extract_x_auth.py         # Extract X cookies from browser/manual input
│   ├── test_search.py            # Smoke test for XReverseClient
│   └── test_whatsapp.py          # Smoke test for WhatsAppClient
│
├── tests/
│   ├── __init__.py
│   ├── conftest.py               # Pytest fixtures
│   ├── test_agent.py             # HiringAgent tests
│   ├── test_filter.py            # Tweet filtering tests
│   └── test_x_client.py          # XReverseClient tests
│
├── ops/
│   ├── Dockerfile                # Python 3.11-slim, non-root user
│   ├── docker-compose.yml        # Orchestration config
│   └── systemd/
│       └── sde-agent.service     # Systemd service definition
│
├── pyproject.toml                # Build system, project metadata, pytest config
├── requirements.txt              # Pip dependencies (generate from pyproject.toml)
├── README.md                     # This file
├── .env.example                  # Environment variable template
└── data/                         # SQLite databases (git-ignored)
    ├── hiring_agent.db           # Main database
    └── hiring_agent_graph.sqlite # LangGraph checkpoint storage
```

---

## 🚀 Quick Start

### Prerequisites
- Python 3.11+
- X (Twitter) account with auth cookies
- OpenAI API key
- Twilio WhatsApp sandbox setup

### Installation

1. **Clone and setup**:
   ```bash
   git clone https://github.com/Nirvanjha2004/Xrary.git
   cd Xrary
   python -m venv venv
   source venv/bin/activate  # Windows: venv\Scripts\activate
   pip install -r requirements.txt
   ```

2. **Extract X auth cookies**:
   ```bash
   python scripts/extract_x_auth.py --browser chrome --output .env
   # Or manually:
   python scripts/extract_x_auth.py --browser manual
   ```

3. **Configure environment** (`.env`):
   ```env
   OPENAI_API_KEY=sk-...
   OPENAI_MODEL=gpt-4o-mini
   
   TWILIO_ACCOUNT_SID=ACxxx
   TWILIO_AUTH_TOKEN=xxx
   TWILIO_WHATSAPP_FROM=whatsapp:+1234567890
   TWILIO_WHATSAPP_TO=whatsapp:+0987654321
   
   X_AUTH_TOKEN=xxx
   X_CT0=xxx
   X_SEARCH_QUERY=SDE intern hiring apply join us
   
   POLL_INTERVAL_MINUTES=10
   LOG_LEVEL=INFO
   ```

4. **Test clients**:
   ```bash
   # Test X search
   python scripts/test_search.py
   
   # Test WhatsApp
   python scripts/test_whatsapp.py
   ```

5. **Run the agent**:
   ```bash
   python -m src.main
   ```

   Expected output (JSON logs to stdout):
   ```json
   {"event": "initializing_hiring_agent_service", "timestamp": "2026-05-01T12:00:00Z"}
   {"event": "database_initialized", "timestamp": "2026-05-01T12:00:01Z"}
   {"event": "scheduler_started", "timestamp": "2026-05-01T12:00:02Z"}
   ```

---

## 🐳 Docker Deployment

### Build & Run

```bash
# Build image
docker build -t hiring-agent:latest -f ops/Dockerfile .

# Run container
docker run -d \
  --name hiring-agent \
  --env-file .env \
  -v ./data:/app/data \
  -v ./logs:/app/logs \
  hiring-agent:latest

# View logs
docker logs -f hiring-agent
```

### Docker Compose

```bash
cd ops
docker-compose up -d

# View logs
docker-compose logs -f hiring-agent

# Stop
docker-compose down
```

### Systemd Service (Linux)

```bash
sudo cp ops/systemd/sde-agent.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable sde-agent
sudo systemctl start sde-agent
sudo journalctl -u sde-agent -f
```

---

## 📊 Agent State & Metrics

The agent tracks state via LangGraph checkpoints:

```python
AgentState:
  tweets: list[Tweet]                          # Raw tweets from X
  filtered_tweets: list[Tweet]                 # After cheap filter + dedup
  judged_tweets: list[tuple[Tweet, JudgeResult]]  # High-confidence hiring posts
  notifications_sent: int                      # Count of WhatsApp alerts
  error_count: int                             # Cumulative errors
  last_run: str | None                         # ISO timestamp of last cycle
```

Database persistence (SeenTweet):
```python
SeenTweet:
  tweet_id: str (unique)
  tweet_text: str
  author_handle: str
  detected_at: datetime
  notified: bool
  confidence_score: float | None
  company: str | None
  role: str | None
```

---

## 🔧 Configuration

### Environment Variables

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `OPENAI_API_KEY` | str | ❌ Required | OpenAI API key |
| `OPENAI_MODEL` | str | `gpt-4o-mini` | LLM model to use |
| `TWILIO_ACCOUNT_SID` | str | ❌ Required | Twilio account SID |
| `TWILIO_AUTH_TOKEN` | str | ❌ Required | Twilio auth token |
| `TWILIO_WHATSAPP_FROM` | str | ❌ Required | Format: `whatsapp:+...` |
| `TWILIO_WHATSAPP_TO` | str | ❌ Required | Format: `whatsapp:+...` |
| `X_AUTH_TOKEN` | str | ❌ Required | X session cookie |
| `X_CT0` | str | ❌ Required | X CSRF token |
| `X_SEARCH_QUERY` | str | `SDE intern hiring...` | X search query |
| `POLL_INTERVAL_MINUTES` | int | `10` | Polling interval |
| `SQLITE_DB_PATH` | str | `data/hiring_agent.db` | Database path |
| `LOG_LEVEL` | str | `INFO` | Logging level |

---

## 🧪 Testing

### Run Tests
```bash
pytest tests/ -v
```

### Test Coverage
- `test_agent.py`: HiringAgent workflow orchestration
- `test_filter.py`: cheap_filter logic and edge cases
- `test_x_client.py`: XReverseClient parsing and errors

### Manual Testing
```bash
# Test X search
python scripts/test_search.py

# Test WhatsApp (sends real message)
python scripts/test_whatsapp.py
```

---

## 📈 Metrics & Monitoring

Logs are JSON-structured for easy parsing:

```json
{
  "event": "hiring_agent_cycle_complete",
  "notifications_sent": 3,
  "error_count": 0,
  "last_run": "2026-05-01T12:10:00Z",
  "timestamp": "2026-05-01T12:10:05Z"
}
```

Key metrics to monitor:
- **`notifications_sent`**: Count of WhatsApp alerts per cycle
- **`error_count`**: Cumulative errors (retry exhaustion, API failures)
- **`tweet_count`** (search node): Raw tweets fetched
- **`filtered_count`** (filter node): After cheap filter + dedup
- **`judged_count`** (judge node): High-confidence posts

---

## 🚧 Future Enhancements

### Short-term
1. **Email Alerts**: Add Gmail/SendGrid integration alongside WhatsApp
2. **Web Dashboard**: Flask/FastAPI UI for viewing alerts, stats, logs
3. **Advanced Filtering**: Location-aware filtering, role-specific keywords (full-stack vs backend vs ML)
4. **Webhook Support**: POST alerts to external services (Slack, Discord, custom endpoints)
5. **Database UI**: sqlite-web optional container for browsing dedup store

### Medium-term
6. **Batch Notifications**: Daily digest instead of real-time alerts
7. **User Subscriptions**: Multi-user support with role/location preferences
8. **LLM Fine-tuning**: Retrain GPT-4o-mini on verified hiring posts
9. **Database Migrations**: Alembic schema versioning and migration management
10. **CI/CD Pipeline**: GitHub Actions for testing, linting, image builds

### Long-term
11. **Multi-Platform Search**: LinkedIn, Indeed, company career pages (web scraping)
12. **Feedback Loop**: User ratings on alerts (relevant? spam?) for model improvement
13. **Auto-Apply**: Integration with application APIs (if available)
14. **Analytics**: BI dashboard (hiring trends, company activity, seasonal patterns)
15. **Mobile App**: Native iOS/Android app for alerts and dashboard

---

## 📝 Technical Stack

| Component | Technology | Purpose |
|-----------|-----------|---------|
| **Scheduling** | APScheduler | Background polling task |
| **Workflow** | LangGraph | DAG-based pipeline orchestration |
| **Search** | httpx (async) | X GraphQL queries |
| **LLM** | OpenAI API | Hiring classification |
| **Notifications** | Twilio | WhatsApp delivery |
| **Database** | SQLAlchemy 2.0 + SQLite | ORM and persistence |
| **Validation** | Pydantic v2 | Data schema + config |
| **Logging** | structlog | JSON structured logs |
| **Retry Logic** | tenacity | Resilient API calls |
| **Testing** | pytest | Unit tests |
| **Containerization** | Docker | Reproducible deployment |

---

## 🔐 Security Considerations

1. **Credentials**: Store `.env` securely (use secrets manager in production)
2. **Rate Limiting**: X API may throttle; built-in retry handles transient failures
3. **LLM Costs**: Monitor OpenAI usage; each judgment costs ~0.001 USD
4. **Non-root User**: Docker runs as `appuser` (not root) for security
5. **Logging**: Avoid logging PII or sensitive data

---

## 📄 License

MIT License - See LICENSE file for details.

---

## 🤝 Contributing

Contributions welcome! Please:
1. Fork the repository
2. Create a feature branch (`git checkout -b feature/my-feature`)
3. Commit changes (`git commit -m "Add my feature"`)
4. Push to branch (`git push origin feature/my-feature`)
5. Open a Pull Request

---

## 📞 Support & Issues

Found a bug? Have a feature request? Open an issue on GitHub:
- [GitHub Issues](https://github.com/Nirvanjha2004/Xrary/issues)

---

**Built with ❤️ by [Nirvanjha2004](https://github.com/Nirvanjha2004)**
