## 0.3.0 (2025-10-25)

### Feat

- **db + bootstrap**: refactor database initialization and enhance role management
- **upload + deduplication**: implement document deduplication and enhance tenant-based operations
- **parsers + docs**: introduce optional Docling parser and set Llama as default
- **tests + repo + service**: implement document listing with pagination and filtering
- **dockerfile + entrypoint**: optimize build cache and enable Uvicorn reload
- **config + docker**: enhance CORS handling and improve environment portability
- **docs + db**: document RLS enforcement and simplify role management in migrations
- **app + config**: enhance middleware setup and update configurations
- **build + deps**: migrate `tenauth` to PyPI and update dependencies
- **app + config**: update SDK references and enable CORS support
- **dockerfile + config**: add essential CLI tools, rebrand project, and bump version
- **parsers + build**: add support for markdown heading-based chunking in Llama parser
- **parsers + config**: enhance Llama parser usability and add environment-based parser switching
- **parsing**: add Llama parser support and developer guide
- **db + schema**: introduce tenant-specific schema support and enforce RLS policies
- **api**: add health probes and enforce authentication on v1 routes
- **observability**: add OpenTelemetry metrics support with OTLP exporter
- **observability + workers**: add OpenTelemetry metrics, tracing, and worker liveness beacons
- **scripts + auth**: enhance docker-build options and update UUID default tenant
- **logging + scripts**: enhance OpenTelemetry integration and streamline Jaeger setup
- **db**: add support for LangChain PGVector tables and tenant isolation with RLS
- **logging + observability**: integrate OpenTelemetry, improve logging, and expand tests
- **docker + logging**: add OpenTelemetry integration and console-based logging
- **db**: add `clear-tables` command for clearing SQLModel-managed table data
- **upload-pipeline**: introduce metadata extraction step and enhance configurability
- **profiles**: refactor and modularize profile registry for enhanced reusability
- **entrypoint**: add SKIP_MIGRATIONS option for database migration control
- **test-profiles**: implement testing infrastructure for processing profiles and parsers
- **container, docs**: add entrypoint for unified web & worker processes; update deployment notes
- **database**: initialize Alembic migrations and apply RLS policies
- **database**: drop conflicting unique constraint for multi-tenant RLS compatibility
- **worker, database, logging**: enhance event-loop compatibility and ingestion pipeline logic
- **logging, configuration**: integrate Loguru for application-wide logging
- **upload-service, monitoring**: integrate Dramatiq task queue and Prometheus metrics support

### Fix

- **logging**: ensure document_id is consistently cast to string in log context

### Refactor

- **db**: update default privileges to use `vectra_alembic_user`
- **db + config**: remove redundant schema creation logic and migrate to static schema references
- **repositories**: convert static methods to instance methods and replace direct class usages
- **tests + conftest**: isolate vectorstore-specific fixtures and clean imports
- **retrieval**: remove unused retrieval schemas, routes, and tests
- **metadata**: remove legacy metadata extraction and strategy implementation
- **extract + repositories**: wrap state handlers in `RunnableLambda` and improve typing
- **entrypoint + Docker**: simplify environment variables, improve runtime layering, and streamline build process
- **logging + observability**: consolidate configurations and enhance OpenTelemetry integration
- **logging + entrypoint**: remove unused scripts, consolidate OTEL configs
- **tests**: simplify metadata persistence; feat(upload): refine extraction/validation
- **config + logging**: simplify configurations and enhance clarity
- **upload-service**: refactor UploadPipeline to use immutable JobCtx for job state management
- **worker**: remove unused Dramatiq `time_limit` and `max_retries` settings from actor definition
