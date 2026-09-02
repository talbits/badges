all: format check

format: prettier black ruff

check: mypy pyright checkblack checkruff checkprettier

prettier:
	uv run ./node_modules/.bin/prettier --write .
pyright:
	uv run ./node_modules/.bin/pyright

mypy:
	uv run mypy .

black:
	uv run black .

ruff:
	uv run ruff check . --fix

checkruff:
	uv run ruff check .

checkprettier:
	uv run ./node_modules/.bin/prettier --check .

checkblack:
	uv run black --check .

checkeditorconfig:
	editorconfig-checker

test:
	@set -eu; \
	TZ=America/New_York node tests/test_datetime.js; \
	node tests/test_public.js; \
	TEST_DATA_DIR=$$(mktemp -d); \
	trap 'status=$$?; rm -rf "$$TEST_DATA_DIR"; exit $$status' EXIT; \
	PYTHONUNBUFFERED=1 \
	DEBUG=true \
	LNBITS_DATA_FOLDER="$$TEST_DATA_DIR" \
	LNBITS_DATABASE_URL="" \
	uv run pytest

install-pre-commit-hook:
	@echo "Installing pre-commit hook to git"
	@echo "Uninstall the hook with uv run pre-commit uninstall"
	uv run pre-commit install

pre-commit:
	uv run pre-commit run --all-files


checkbundle:
	@echo "skipping checkbundle"
