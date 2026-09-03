# Blin Bot — architecture

## Goal

Blin Bot is moving to a Dashboard-first architecture. Discord is the runtime platform; server configuration is managed outside the bot source code.

```text
Blin Dashboard
      │
      │ HTTPS / JSON API
      ▼
   Blin Bot API
      │
      ├── Discord Gateway / REST
      │
      └── SQLite now → PostgreSQL later
```

## Configuration

Discord role/channel/category IDs are **runtime data**. They must never be committed as constants in Python modules. The Dashboard will obtain the current guild objects from the bot and save the selected IDs in the guild configuration.

The logical names `DN` and `PHX` are labels used by the current application workflow; they are not Discord IDs and can be renamed/reconfigured later.

## Database

`database.py` owns persistent configuration and module data. `storage.py` is currently a compatibility facade for existing modules and stores its state in SQLite. If an old `data.json` exists and the database has no state yet, it is imported once.

The database contains:

- guilds;
- per-guild configuration;
- enabled modules and module settings;
- persistent bot state;
- DM notification consent;
- contract blocks;
- disciplinary warnings;
- reaction-role configuration.

## Modules

The initial module registry is:

- applications;
- vacations;
- contracts;
- discipline;
- dm_notifications;
- reaction_roles.

Modules are enabled/disabled per guild through the configuration API.

## Dashboard API

The current API is intentionally small and stable so the website can be built against it:

- `GET /health`
- `GET /api/guilds`
- `GET /api/guilds/{guild_id}/objects`
- `GET /api/guilds/{guild_id}/config`
- `PUT /api/guilds/{guild_id}/config`
- `GET /api/guilds/{guild_id}/modules`
- `PUT /api/guilds/{guild_id}/modules`
- `GET /api/guilds/{guild_id}/contracts`
- `POST /api/guilds/{guild_id}/contracts`
- `PUT /api/guilds/{guild_id}/consent`

The temporary API authentication uses `X-Blin-Secret`. Before production use, the Dashboard should switch this to Discord OAuth2 plus server-level authorization. The shared secret must not be exposed in browser JavaScript.

## Discord safety

The bot does not attempt to bypass Discord restrictions. DM notifications are sent only when the corresponding consent record is enabled, and failed DMs are handled as delivery failures rather than treated as guaranteed delivery.

## Deployment direction

Development can use SQLite. Production should use PostgreSQL behind the API service. The website should never connect directly to the database; it communicates with the API only.
