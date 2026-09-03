# Blin Bot

Blin Bot is a Discord automation bot built around a **Dashboard-first** configuration model.

The long-term architecture is:

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

                    persistent configuration/state
                              │
                              ▼
                         SQLite / PostgreSQL
```

## Important design rule

**Discord IDs are not configuration constants in the source code.**

The bot discovers the current guild roles, channels and categories from Discord. The Dashboard displays them by name and stores the selected Discord IDs in the database as runtime configuration.

This means the same bot build can serve multiple unrelated Discord servers without a separate code/config file for each server.

## Modules

The bot is being split into independently configurable modules:

- applications — recruitment applications and tickets;
- vacations — vacation requests, active vacation list and automatic expiry;
- contracts — configurable contract/bonus forms;
- discipline — strict-warning workflow and history;
- dm_notifications — opt-in direct-message notifications;
- reaction_roles — configurable role buttons.

Module state is stored per guild and can be enabled/disabled through the Dashboard API.

## Database

`database.py` is the persistent configuration layer. The default backend is SQLite for simple deployment and development.

The database stores:

- guilds and their enabled state;
- per-guild Discord configuration;
- module switches and module settings;
- persistent bot state;
- DM consent;
- contract blocks;
- disciplinary warning history;
- reaction-role configurations.

If an existing installation has `data.json`, the compatibility layer can import it once into the database.

## Dashboard API

The bot exposes a small JSON API for the Dashboard:

- `GET /health`
- `GET /api/guilds`
- `GET /api/guilds/{guild_id}/objects`
- `GET|PUT /api/guilds/{guild_id}/config`
- `GET|PUT /api/guilds/{guild_id}/modules`
- `GET|POST /api/guilds/{guild_id}/contracts`
- `GET /api/guilds/{guild_id}/warnings`
- `GET|POST /api/guilds/{guild_id}/reaction-roles`
- `PUT /api/guilds/{guild_id}/consent`

For development the API can be protected with `X-Blin-Secret`. **Do not put this secret into browser JavaScript.** Production authentication is intended to use Discord OAuth2 in a Dashboard backend, which then calls the bot API server-to-server.

## Environment

Copy `.env.example` and set at least:

```text
DISCORD_TOKEN=...
BLIN_API_SECRET=...
```

Optional settings include the database path, API host/port, allowed frontend origins, timezone and Discord OAuth2 credentials.

## Server provisioning

`provisioning.py` contains the safe foundation for Dashboard-driven server setup. It creates only missing roles/categories/text channels described by a blueprint and never deletes existing Discord objects.

The Dashboard can therefore provide a guided "Create structure" workflow without requiring an administrator to copy Discord IDs into configuration.

## Discord safety

The bot does not attempt to bypass Discord restrictions. Direct messages are opt-in and delivery failures are handled as normal failures. Discord permissions and role hierarchy remain authoritative.

## Current status

The repository is in the migration phase from the original Discord-configured implementation to the Dashboard-first architecture. Existing application/vacation workflows are retained while their configuration is progressively moved behind the runtime configuration layer.
