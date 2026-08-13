default: test

run: test

test:
    uv run pytest -q

watch:
    uv run watchfiles 'uv run pytest -q' src tests
