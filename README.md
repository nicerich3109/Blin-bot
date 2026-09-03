# Blin Bot

Blin Bot is a Discord automation bot built around a **Dashboard-first** configuration model.

```text
Discord user
     │
     ▼
Blin Dashboard ── Discord OAuth2 ──► Dashboard backend
                                      │
                                      │ authenticated API
                                      ▼
                                   Blin Bot
                                      │
                                      ▼
                                  Discord API
                                      │
                                      ▼
                         SQLite / PostgreSQL
```

## Architecture rules

- Discord object IDs are **runtime data**, never server-specific constants in Python source.
- Every guild has its own configuration and module switches.
- The Dashboard selects live roles, categories and channels by name; the selected IDs are stored only in the database.
- The same bot build can serve multiple unrelated Discord servers.
- Discord permissions and role hierarchy remain authoritative.

## Modules

- `applications` — recruitment applications, tickets and recruiter calls;
- `vacations` — vacation requests, active list and automatic expiry;
- `contracts` — configurable contract/bonus forms;
- `discipline` — strict-warning workflow and history;
- `dm_notifications` — explicit opt-in system DMs;
- `reaction_roles` — configurable role-button configurations.

Modules are enabled/disabled per guild through the Dashboard API.

## Database

`database.py` is the persistence/configuration layer. SQLite is the default local backend; the API boundary is intentionally storage-agnostic so production deployment can move to PostgreSQL.

Stored data includes guild configuration, module settings, bot state, DM consent, contracts, disciplinary history and reaction-role configurations. The legacy `data.json` is imported by the compatibility storage layer when no database state exists.

## Dashboard API

The bot exposes:

- `GET /health`
- `GET /api/guilds`
- `GET /api/guilds/{guild_id}/objects`
- `GET|PUT /api/guilds/{guild_id}/config`
- `GET|PUT /api/guilds/{guild_id}/modules`
- `GET|POST /api/guilds/{guild_id}/contracts`
- `POST /api/guilds/{guild_id}/contracts/{contract_id}/publish`
- `POST /api/guilds/{guild_id}/provision`
- `GET /api/guilds/{guild_id}/warnings`
- `GET|POST /api/guilds/{guild_id}/reaction-roles`
- `PUT /api/guilds/{guild_id}/consent`

For development the API can use `X-Blin-Secret`. **Never expose this secret to browser JavaScript.** Production Dashboard authentication should be Discord OAuth2 in the Dashboard backend, which calls the bot API server-to-server. Discord documents OAuth2 scopes and permission handling separately from bot authorization. citeturn0search9turn0search4

## Server provisioning

`provisioning.py` provides Dashboard-driven creation of missing roles, categories and text channels from a blueprint. Existing objects are reused and nothing is deleted automatically.

## Discord safety

The bot does not attempt to bypass Discord restrictions. System DMs require explicit consent and delivery failures are handled normally. Role operations remain subject to Discord's role hierarchy: a bot can grant a role only when that role is below the bot's highest role. citeturn0search2

## Configuration

Copy `.env.example` and set at minimum:

```text
DISCORD_TOKEN=...
BLIN_API_SECRET=...
```

Optional values configure the database path, API listener, CORS origins, timezone and server-side Discord OAuth2 credentials.

## Status

The bot foundation is now Dashboard-first: guild-scoped configuration, persistent storage, module switches, provisioning and an API boundary are in place. Existing recruitment/vacation flows use runtime configuration, and processed recruitment tickets are archived instead of deleted with applicant access removed.

The next repository is `Blin-website`, which will become the user-facing Dashboard over this API.
