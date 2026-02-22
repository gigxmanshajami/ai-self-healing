# 🚀 AI Self-Healing Web Scraper

An intelligent web scraping solution with ML-powered **self-healing capabilities**. When CSS selectors break due to website changes, the scraper automatically detects failures and uses machine learning to identify alternative selectors — no manual intervention required.

## ✨ Features

- **🔄 Self-Healing**: Automatically recovers from selector failures using ML predictions
- **🧠 ML-Powered**: Logistic Regression model trained on DOM structure patterns
- **📊 Dashboard**: Real-time metrics, healing trends, and model performance
- **📝 Logging**: Comprehensive healing history and audit trail
- **⚡ Fast**: Async operations with parallel healing attempts
- **🎯 Accurate**: 89%+ accuracy with confidence scoring

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                        FRONTEND (Next.js)                           │
│  ┌───────────┬───────────┬──────────┬──────────────┬───────────┐   │
│  │ Dashboard │   Scrape  │   Logs   │ Model Insights│ Settings │   │
│  └───────────┴───────────┴──────────┴──────────────┴───────────┘   │
└─────────────────────────────┬───────────────────────────────────────┘
                              │ REST API
┌─────────────────────────────▼───────────────────────────────────────┐
│                        BACKEND (FastAPI)                            │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │                       API Layer                               │  │
│  │  POST /scrape │ POST /heal │ GET /logs │ GET /models/status  │  │
│  └──────────────────────────────────────────────────────────────┘  │
│                              │                                       │
│  ┌────────────────┬──────────▼──────────┬────────────────────────┐ │
│  │    Scraper     │     AI Engine       │       Storage          │ │
│  │  ┌──────────┐  │  ┌───────────────┐  │  ┌─────────────────┐   │ │
│  │  │ Selenium │  │  │Feature Extract│  │  │    SQLite DB    │   │ │
│  │  │  Driver  │──│──│    + Model    │──│──│  selector_hist  │   │ │
│  │  └──────────┘  │  │   Predict     │  │  │  healing_logs   │   │ │
│  │  ┌──────────┐  │  └───────────────┘  │  └─────────────────┘   │ │
│  │  │ Failure  │  │  ┌───────────────┐  │                        │ │
│  │  │ Detector │  │  │ XPath Generate│  │                        │ │
│  │  └──────────┘  │  └───────────────┘  │                        │ │
│  └────────────────┴─────────────────────┴────────────────────────┘ │
└─────────────────────────────────────────────────────────────────────┘
```

## 🛠️ Tech Stack

| Layer | Technology |
|-------|------------|
| Frontend | Next.js 16, TypeScript, Tailwind CSS, Recharts, React Query |
| Backend | Python, FastAPI, Pydantic, Loguru |
| Scraping | Selenium, BeautifulSoup, lxml |
| ML | scikit-learn (Logistic Regression, RandomForest) |
| Database | SQLite (aiosqlite) |

## 🚀 Quick Start

### Prerequisites
- Python 3.10+
- Node.js 18+
- Chrome browser (for Selenium)

### Backend Setup

```bash
cd backend
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
uvicorn main:app --reload
```

### Frontend Setup

```bash
cd frontend
npm install
npm run dev
```

Open [http://localhost:3000](http://localhost:3000) - Dashboard ready!

## 📡 API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/v1/scrape` | Execute scrape job with optional healing |
| POST | `/api/v1/heal` | Manually trigger healing for a selector |
| GET | `/api/v1/logs` | Get healing logs with pagination |
| GET | `/api/v1/models/status` | Get ML model metrics and stats |
| GET | `/api/v1/selectors/history` | Get selector change history |

## 🔄 Self-Healing Flow

```
1. Try Selector     →  CSS/XPath fails
2. Detect Failure   →  Identify failure type
3. Scan DOM         →  Extract all elements
4. Extract Features →  71 ML features per element
5. ML Prediction    →  Score candidates
6. Generate XPath   →  Create stable selector
7. Retry Scraping   →  Verify new selector works
8. Store Success    →  Learn from change
```

## 🧠 ML Model Details

- **Algorithm**: Logistic Regression (primary), RandomForest (option)
- **Features**: 71 total including tag encoding, similarity scores, DOM position
- **Training**: Synthetic + real healing data
- **Accuracy**: ~89% cross-validated

See [AI_MODEL.md](docs/AI_MODEL.md) for detailed ML documentation.

## 📁 Project Structure

```
ai-self-healing-scraper/
├── backend/
│   ├── api/           # FastAPI routes & schemas
│   ├── ai_engine/     # ML model & XPath generator
│   ├── scraper/       # Selenium driver & failure detection
│   ├── storage/       # SQLite DB management
│   └── main.py        # Application entry
├── frontend/
│   ├── app/           # Next.js pages
│   ├── components/    # React components
│   └── lib/           # API client & providers
└── docs/              # Documentation
```

## 📊 Dashboard Preview

The dashboard provides:
- **Stats**: Total healings, success rate, avg confidence, heal time
- **Charts**: Healing trends, strategy distribution
- **Logs**: Recent healing events with confidence scores
- **Model**: Live ML model metrics and feature importance

## 🎯 Interview Ready

### Key Discussion Points
1. **Why Self-Healing?** - Reduces maintenance, handles dynamic sites
2. **ML Choice**: Logistic Regression for speed & interpretability
3. **Feature Engineering**: DOM structure analysis, similarity scoring
4. **Scalability**: Async design, background tasks, model caching

### Demo Scenarios
- Normal scrape → Success
- Selector change → Auto-heal → Recovery
- Low confidence → Manual review

## 📄 License

MIT License - See [LICENSE](LICENSE) for details.

---

Built with ❤️ for intelligent web scraping
# ai-self-healing
