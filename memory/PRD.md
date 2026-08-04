# ARI AI - Competitor Price Tracking System PRD

## Original Problem Statement
Arıgastro e-commerce competitor price tracking + SEO generator + İkas API integration

## Tech Stack
React + FastAPI + MongoDB + ScraperAPI + OpenAI GPT-4o + APScheduler + İkas GraphQL API

## All Features
1. JWT Auth + admin seeding
2. Product Import (Google Merchant Feed)
3. Category Management (track/untrack, Turkish char support, brand matching)
4. AI Product Matching + Akakçe Panel JSON Import (0 credit)
5. Price Tracking (parallel workers, category filter, individual exclusion)
6. SEO Generator (AI content + ReactMarkdown rendering)
7. **İkas API Integration** (push SEO content directly to İkas)
8. Dashboard (stats + ScraperAPI credits)
9. Settings (system status, scheduler, user management CRUD)
10. Guide Page
11. APScheduler (Feed: 01:00 daily, Price check: 00:00 TR daily)
12. Stuck task auto-recovery

## İkas API
- Auth: OAuth2 Client Credentials → `https://api.myikas.com/api/admin/oauth/token`
- GraphQL: `https://api.myikas.com/api/v2/admin/graphql`
- Product search: `listProduct(search, pagination)`
- Product update: `updateProduct(input: {id, description, metaData: {pageTitle, description}})`
- Client ID: 0cdef9f7-8c75-4ec3-8037-376fa050ce30

## Key Credentials
- Admin: arigastro / Arigastro2026!
- ScraperAPI: c214e73952e0b11ef5c0398aed5b55be
- İkas Client ID: 0cdef9f7-8c75-4ec3-8037-376fa050ce30
- Akakçe Panel: info@arigastro.com / Ari7065626
- Server: 161.97.122.111 (Contabo VPS)
- Domain: arigastro-ai.com
