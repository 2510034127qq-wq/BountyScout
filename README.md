# BountyScout API (TypeScript/Express)

This repository now includes a minimal **Express** API written in **TypeScript** that demonstrates the fix for the reported issue:

## Issue
> **POST /api/proposals endpoint missing authentication middleware**  

The `/api/proposals` route must be protected so that only authenticated callers can create proposals.

## Fix
- Added `src/middleware/auth.ts` – a simple authentication middleware that checks for a `Bearer secret-token` header.
- Created `src/routes/proposals.ts` where the `POST /api/proposals` route now uses the `authMiddleware`.
- Set up an Express application in `src/app.ts` and a server entry point `src/server.ts`.
- Included a Jest + Supertest test suite (`test/proposals.test.ts`) that verifies:
  * 401 responses when auth is missing or invalid
  * 400 responses for malformed payloads
  * 201 success when a valid token and payload are supplied

## Running the project

