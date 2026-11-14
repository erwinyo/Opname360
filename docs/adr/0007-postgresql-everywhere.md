# PostgreSQL in every environment, including tests

Concurrent POS sales and FIFO consumption of Cost Layers need row-level locking, which SQLite (used by the initial scaffold) doesn't provide. Testing on a different database than production would hide exactly those bugs, so development and tests run PostgreSQL in Docker, and schema changes go through Alembic migrations rather than `create_all`.
