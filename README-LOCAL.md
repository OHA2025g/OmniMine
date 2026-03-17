# OmniMine - AI-Powered Opinion Mining Platform

Enterprise-grade customer feedback intelligence platform with AI-powered sentiment analysis, smart routing, and closed feedback loop.

## Features

### Core Features
- **AI Sentiment Analysis** - GPT-5.2 powered sentiment, emotion, and theme detection
- **Multi-Source Feedback** - Aggregate from Twitter, Facebook, YouTube, Email, Support Tickets
- **Real-Time Dashboard** - KPIs, sentiment trends, source distribution charts
- **Closed Feedback Loop** - Case management, assignment, resolution tracking

### Smart Routing (AI-Powered)
- **Intelligent Case Assignment** - AI analyzes cases and matches with best agent
- **Agent Skill Management** - Configure skills, workload capacity, availability
- **Performance Tracking** - Satisfaction scores, resolution time metrics

### Admin Features
- **Social Media Configuration** - Configure platform URLs and API keys
- **SLA Management** - Configurable SLA hours per priority level
- **Email Notifications** - Alerts for negative feedback and SLA breaches
- **Export** - CSV/PDF exports for feedback, cases, and analytics

## Tech Stack

- **Frontend**: React 18, Tailwind CSS, Shadcn/UI, Recharts
- **Backend**: FastAPI, Python 3.11+
- **Database**: MongoDB
- **AI**: OpenAI GPT-5.2 (via Emergent Integration)
- **Email**: Resend

## Local Setup

### Prerequisites
- Node.js 18+
- Python 3.11+
- MongoDB (local or cloud)
- OpenAI API key or Emergent LLM key

### Backend Setup

```bash
cd backend

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env with your settings:
# - MONGO_URL=mongodb://localhost:27017
# - DB_NAME=omnimine
# - EMERGENT_LLM_KEY=your_key_here (or use OpenAI directly)
# - RESEND_API_KEY=your_resend_key (optional, for email notifications)

# Run the server
uvicorn server:app --host 0.0.0.0 --port 8001 --reload
```

### Frontend Setup

```bash
cd frontend

# Install dependencies
yarn install

# Configure environment
cp .env.example .env
# Edit .env:
# - REACT_APP_BACKEND_URL=http://localhost:8001

# Run the development server
yarn start
```

### Environment Variables

#### Backend (.env)
```
MONGO_URL=mongodb://localhost:27017
DB_NAME=omnimine
CORS_ORIGINS=*
EMERGENT_LLM_KEY=sk-emergent-xxxxx  # For AI features
JWT_SECRET_KEY=your-secret-key
RESEND_API_KEY=re_xxxxx  # Optional, for email notifications
SENDER_EMAIL=onboarding@resend.dev
```

#### Frontend (.env)
```
REACT_APP_BACKEND_URL=http://localhost:8001
```

## API Endpoints

### Authentication
- `POST /api/auth/register` - Register new user
- `POST /api/auth/login` - Login and get JWT token
- `GET /api/auth/me` - Get current user

### Feedback
- `POST /api/feedback` - Create and analyze feedback
- `GET /api/feedback` - List feedbacks with filters
- `POST /api/feedback/bulk` - Bulk import feedbacks

### Cases (Closed Feedback Loop)
- `POST /api/cases` - Create case from feedback
- `GET /api/cases` - List cases with filters
- `PUT /api/cases/{id}/assign` - Assign case to agent
- `PUT /api/cases/{id}/resolve` - Resolve case

### Smart Routing
- `GET /api/agents/profiles` - List agent profiles
- `PUT /api/agents/profiles/{id}` - Update agent skills
- `POST /api/routing/analyze/{case_id}` - AI routing analysis
- `POST /api/routing/auto-assign/{case_id}` - Auto-assign case

### Analytics
- `GET /api/analytics/overview` - Dashboard KPIs
- `GET /api/analytics/sentiment-trends` - Sentiment over time
- `GET /api/analytics/themes` - Top themes

### Export
- `POST /api/export/feedback/csv` - Export feedback CSV
- `POST /api/export/cases/csv` - Export cases CSV
- `POST /api/export/analytics/pdf` - Export analytics PDF

## User Roles

| Role | Permissions |
|------|-------------|
| Admin | Full access, user management, system settings |
| Manager | Case management, agent assignment, reports |
| Agent | Handle assigned cases, view feedback |
| Analyst | View dashboards, analytics, reports |

## Default Test Credentials

After seeding demo data:
- Admin: `admin2@omnimine.com` / `admin123`
- Agent: `agent1@omnimine.com` / `agent123`

## Seeding Demo Data

After logging in as admin, click "Load Demo Data" button on the dashboard to populate sample feedbacks and cases.

## License

MIT License - See LICENSE file for details.

---

Built with ❤️ using Emergent AI
