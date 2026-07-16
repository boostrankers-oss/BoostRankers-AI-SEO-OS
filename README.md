# Boost Rankers AI SEO OS

A full-stack AI-powered SEO operating system for agencies. Runs a multi-agent
audit engine that analyzes technical SEO, content, local signals, schema, EEAT,
internal linking, competitors, backlinks, and AI search readiness — with results
streaming live to a polished React dashboard.

## Tech Stack

**Frontend:** React 19, TypeScript, Tailwind CSS, shadcn/ui, Recharts, Framer Motion
**Backend:** Python 3.14, FastAPI, httpx, BeautifulSoup, lxml, Anthropic Claude API
**Streaming:** Server-Sent Events (SSE) via native Fetch ReadableStream

## Features

- **Live Audit Engine** — 10 agents stream findings in real-time via SSE
- **Claude AI Integration** — Deep SEO analysis powered by Anthropic's Claude
- **Dashboard** — KPI cards, score trend chart, overall health gauge, monthly tasks
- **Client Management** — create and manage client profiles with SEO history
- **New Audit** — enter URL, keyword, location, competitors → watch agents run live
- **Report Export** — download audit results as Markdown
- **Dark Mode** — emerald/teal themed professional UI
- **Offline Fallback** — built-in simulator runs if backend is unavailable

## Quick Start

### Frontend
