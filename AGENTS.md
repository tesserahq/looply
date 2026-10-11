# Looply

## Scope
- Looply doesn't store or serve images/assets. Campaign and template images are uploaded by the portals (looply-portal, sendly-portal) directly to Vaulta and embedded in the HTML as Vaulta URLs — bugs about email images belong there, not here (see tesserahq/looply-portal#168).

## Testing
- Always run pytest with `ENV=test` set explicitly, e.g. `ENV=test poetry run pytest ...` — otherwise `Settings` silently falls back to the real `looply` dev database instead of `looply_test` (a `.env`-loading bug: `app/config.py`'s `Settings` config class is named `ConfigDict`, not `Config`/`model_config`, so pydantic-settings v2 never reads `.env`). A `relation "X" already exists` error during the alembic-migration test setup is the signature of this misconfiguration.
