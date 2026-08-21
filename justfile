default: test

run: test

test:
    uv run pytest -q

watch:
    uv run watchfiles 'uv run pytest -q' src tests

# Build fresh dist artifacts and publish to PyPI. The token stays in
# 1Password: op resolves the op:// reference in .env at runtime (Touch ID
# prompt) and injects it into uv's environment only.
publish:
    rm -rf dist
    uv build
    op run --env-file=.env -- uv publish
