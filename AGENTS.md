# Looply

## Scope
- Looply doesn't store or serve images/assets. Campaign and template images are uploaded by the portals (looply-portal, sendly-portal) directly to Vaulta and embedded in the HTML as Vaulta URLs — bugs about email images belong there, not here (see tesserahq/looply-portal#168).

## Testing
- Always run pytest with `ENV=test` set explicitly, e.g. `ENV=test poetry run pytest ...` — otherwise `Settings` silently falls back to the real `looply` dev database instead of `looply_test` (a `.env`-loading bug: `app/config.py`'s `Settings` config class is named `ConfigDict`, not `Config`/`model_config`, so pydantic-settings v2 never reads `.env`). A `relation "X" already exists` error during the alembic-migration test setup is the signature of this misconfiguration.

## Database migrations

- Migrations run only in the API's `start.sh`. During a deploy, old and new containers overlap (the API rolls; workers deploy separately), so every migration must work with the previous release's code.
- One release: additive changes (nullable column or one with a server default, table, index).
- Two releases: dropping or renaming a column or table, adding `NOT NULL`, or changing a type. Release 1 stops reading and writing it; a later release runs the migration.
- See [Database migrations](https://github.com/mylinden-tech/infra/blob/main/docs/linden-continuous-delivery.md#database-migrations) and mylinden-tech/infra#260.

## Shared Tessera docs

Cross-service knowledge lives in [tesserahq/docs](https://github.com/tesserahq/docs) (locally `~/sites/tesserahq/docs` when available): the glossary, service ownership, and Custos authorization conventions. Read it before writing or reviewing a PRD, or changing authorization, project scoping, or asset classification.
