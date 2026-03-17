# OmniMine - Product Requirements Document

## Overview
OmniMine is an AI-Powered Opinion Mining & Closed Feedback Intelligence Platform that captures, analyzes, and acts upon customer feedback across multiple digital channels.

## Original Problem Statement
Build an enterprise-grade opinion mining tool featuring:
- Multi-Platform Feedback Aggregation
- AI-powered Opinion Mining Engine (sentiment, emotion, theme extraction)
- Real-Time Monitoring with alerts
- Closed Feedback Loop (assignment, SLA tracking, resolution, surveys)
- Executive Dashboard & Reporting
- Role-based User Management

## User Choices (Jan 2026)
- AI Provider: OpenAI GPT-5.2 (via Emergent LLM Key)
- Authentication: JWT-based custom auth
- Theme: Light theme
- Data Sources: Both manual entry + demo data (API integrations ready for future)

## User Personas
1. **CX Leadership** - Uses dashboards for decision-making
2. **Marketing Teams** - Brand sentiment monitoring
3. **Product Teams** - Feature improvement insights
4. **Support Teams** - Issue resolution via CFL
5. **Data Analysts** - Deep analytics and reporting

## Core Requirements (Static)
- [ ] Multi-source feedback ingestion
- [ ] AI-powered sentiment analysis
- [ ] Emotion detection
- [ ] Theme/topic extraction
- [ ] Real-time alerting
- [ ] Case management (CFL)
- [ ] Resolution tracking
- [ ] Post-resolution surveys
- [ ] Executive dashboards
- [ ] Role-based access control

## What's Been Implemented (Jan 2026)

### Backend (FastAPI + MongoDB)
- ✅ JWT Authentication (register, login, token refresh)
- ✅ User Management with RBAC (Admin, Manager, Agent, Analyst)
- ✅ Feedback CRUD with AI Analysis
- ✅ GPT-5.2 Sentiment Analysis (positive/neutral/negative)
- ✅ Emotion Detection (joy, anger, sadness, etc.)
- ✅ Theme Extraction (product quality, customer service, etc.)
- ✅ Sarcasm Detection
- ✅ Cases Management (CFL - create, assign, resolve)
- ✅ Resolution Logging
- ✅ Survey Recording
- ✅ Alerts System (auto-alerts for negative feedback)
- ✅ Teams Management
- ✅ Analytics APIs (overview, trends, distributions)
- ✅ Demo Data Seeding

### Frontend (React + Tailwind + Shadcn UI)
- ✅ Modern light theme with Manrope + IBM Plex Sans fonts
- ✅ Professional login/register pages
- ✅ Executive Dashboard with KPIs
- ✅ Sentiment trends chart (Recharts)
- ✅ Source distribution pie chart
- ✅ Feedback list with filtering
- ✅ Feedback detail with AI analysis display
- ✅ Cases list and management
- ✅ Case assignment and resolution
- ✅ Analytics page with multiple charts
- ✅ Alerts page
- ✅ Surveys page
- ✅ Settings page (users & teams)
- ✅ Responsive sidebar navigation
- ✅ Toast notifications (Sonner)

## Prioritized Backlog

### P0 - Completed ✅
- Core feedback ingestion
- AI sentiment/theme analysis
- Dashboard & analytics
- CFL basics

### P1 - Next Phase
- Real API integrations (Twitter, Facebook, YouTube)
- Email notifications for alerts
- SLA breach tracking & escalation
- Export to CSV/PDF
- Bulk operations on feedback

### P2 - Future
- Multi-language support
- Voice analytics
- Video sentiment analysis
- AI auto-resolution suggestions
- WhatsApp/Slack integrations

## Technical Architecture
```
Frontend (React) → Backend (FastAPI) → MongoDB
                         ↓
              OpenAI GPT-5.2 (via Emergent)
```

## API Endpoints
- `POST /api/auth/register` - User registration
- `POST /api/auth/login` - User login
- `GET /api/auth/me` - Get current user
- `POST /api/feedback` - Create & analyze feedback
- `GET /api/feedback` - List feedbacks with filters
- `POST /api/cases` - Create case from feedback
- `PUT /api/cases/{id}/assign` - Assign case
- `PUT /api/cases/{id}/resolve` - Resolve case
- `POST /api/surveys` - Record survey response
- `GET /api/alerts` - Get alerts
- `GET /api/analytics/*` - Various analytics endpoints

## Phase 3 Implementation (Jan 2026)

### Smart Routing Features Added
- ✅ **AI-Powered Case Analysis** - GPT-5.2 analyzes case content to determine required skills, complexity, and priority
- ✅ **Agent Skill Management** - 10 configurable skills (Technical Support, Billing, Product Issues, Complaints, etc.)
- ✅ **Agent Profile Management** - Workload capacity, availability status, shift hours, performance tracking
- ✅ **Intelligent Matching Algorithm** - Scores agents based on skill match (40%), workload (30%), satisfaction (20%), speed (10%)
- ✅ **Auto-Assignment** - One-click assignment to best matching agent
- ✅ **Alternative Recommendations** - Shows backup agents with match scores
- ✅ **Bulk JSON Import** - Import multiple feedbacks via JSON array
- ✅ **Scheduled Reports API** - Create/manage scheduled report configurations

### New API Endpoints
- `GET /api/agents/profiles` - List all agent profiles with skills
- `GET /api/agents/skills` - List available skills
- `PUT /api/agents/profiles/{user_id}` - Update agent skills/workload
- `POST /api/routing/analyze/{case_id}` - AI analysis for routing
- `POST /api/routing/auto-assign/{case_id}` - Auto-assign to best agent
- `POST /api/import/feedback/json` - Bulk feedback import
- `GET/POST/DELETE /api/reports/scheduled` - Scheduled reports management

### UI Enhancements
- ✅ **Smart Routing Page** - Agent profiles table with skills, workload bars, performance metrics
- ✅ **Edit Agent Dialog** - Skill selection grid, availability toggle, workload capacity
- ✅ **Cases Page** - Lightning icon for smart routing on unassigned cases
- ✅ **Smart Routing Dialog** - AI analysis results, recommended agent with confidence score, alternatives

## Next Tasks
1. Implement live social media API ingestion (requires platform API keys)
2. Add scheduled report email delivery (cron job)
3. Implement real-time workload updates via WebSocket
4. Add agent performance analytics dashboard
5. Implement bulk CSV file upload with drag-and-drop
