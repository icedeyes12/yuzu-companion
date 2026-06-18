---
name: yuzu-db-architecture
description: Enforce the Facade database architecture, PostgreSQL pgvector usage, and async queries for yuzu-companion. Use whenever modifying database interactions.
---
# Database Architecture & pgvector Standards

## Architectural Rules
1. **Facade Pattern Only**: NEVER write direct database connections or execute queries inside service logic (e.g., `services/` or core `memory/`). All DB interactions MUST pass through a Facade (`db/facade.py` or `memory/db_memory_facade.py`).
2. **Raw SQL, No ORM**: Do not use Object-Relational Mappers (ORM) like SQLAlchemy. We use raw SQL exclusively.
3. **Query Isolation**: All SQL query strings must be isolated in dedicated files (`db/queries.py` or `memory/db_memory_queries.py`). Do not inline SQL strings.
4. **Asynchronous Execution**: Always use the async DB models (`db/models_async.py`). No synchronous/blocking DB calls.

## pgvector & Memory Rules
- **Vector Database**: PostgreSQL with the `pgvector` extension. Target the `semantic_facts` table for memory logic.
- **Embedding Model**: Model is strictly `Qwen/Qwen3-Embedding-8B`.
- **Dimensions**: Strictly fixed at **4096**.

## Experimental Scripts Warning
- **Hands Off `scripts/`**: The files inside the `scripts/` directory (e.g., dedupe, cleanup, reembed scripts) are for one-off migrations or experimental maintenance ONLY. 
- DO NOT execute these scripts or integrate their logic into the core application runtime without explicit, direct orders from the user.
