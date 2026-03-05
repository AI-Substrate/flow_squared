# Domain Map

> Auto-maintained by plan commands. Shows all domains and their contract relationships.
> Domains are first-class components — this diagram is the system architecture at business level.

```mermaid
flowchart LR
    classDef business fill:#E3F2FD,stroke:#2196F3,color:#000
    classDef infra fill:#F3E5F5,stroke:#9C27B0,color:#000
    classDef new fill:#FFF3E0,stroke:#FF9800,color:#000
    classDef planned fill:#E8F5E9,stroke:#4CAF50,color:#000

    %% Infrastructure domains
    config["⚙️ configuration\nConfigurationService\nFS2ConfigurationService"]:::infra
    graphstore["💾 graph-storage\nGraphStore · GraphService\nCodeNode · ContentType"]:::infra

    %% Business domains
    search["🔍 search\nSearchService\nQuerySpec · SearchResult"]:::business

    %% NEW planned domains (028-server-mode)
    server["🌐 server\nFastAPI · Ingestion\nDashboard · REST API"]:::infra
    auth["🔑 auth\nAuthService · RLS\nTenants · API Keys"]:::planned

    %% Informal domains (not yet extracted)
    cli["📺 cli-presentation\n(informal)"]:::new
    indexing["📦 indexing\n(informal)"]:::new
    embedding["🧠 embedding\n(informal)"]:::new

    %% Contract dependencies (existing)
    search -->|GraphStoreProtocol| graphstore
    search -->|ConfigurationService| config
    search -.->|EmbeddingAdapter| embedding
    graphstore -->|ConfigurationService| config
    cli -->|SearchService| search
    cli -->|GraphService| graphstore
    cli -->|ConfigurationService| config
    indexing -->|GraphStore| graphstore
    indexing -->|ConfigurationService| config
    embedding -->|ConfigurationService| config

    %% NEW dependencies (028-server-mode)
    server -->|PostgreSQLGraphStore| graphstore
    server -->|SearchService + PgvectorMatcher| search
    server -->|ServerDatabaseConfig| config
    server -->|AuthService + API key middleware| auth
    auth -->|ConfigurationService| config
    cli -.->|RemoteGraphStore HTTP| server
```

## Legend

- **Blue**: Business domains (user-facing capabilities)
- **Purple**: Infrastructure domains (cross-cutting technical capabilities)
- **Orange**: Informal domains (identified but not yet formally extracted)
- **Green**: Planned domains (028-server-mode, not yet implemented)
- **Solid arrows** (→): Contract dependency (A consumes B's contract)
- **Dashed arrows** (-.->): Dependency on informal domain or planned contract

## Domain Health Summary

| Domain | Contracts Out | Consumers | Contracts In | Providers | Status |
|--------|--------------|-----------|-------------|-----------|--------|
| configuration | ConfigurationService, FakeConfigurationService, 12 config models | graph-storage, search, cli, indexing, embedding, server, auth | — | — | ✅ Healthy |
| graph-storage | GraphStore, GraphService, CodeNode, ContentType | search, cli, indexing, server | ConfigurationService | configuration | ✅ Healthy |
| search | SearchService, QuerySpec, SearchResult, SearchMode | cli, server | GraphStoreProtocol, ConfigurationService, EmbeddingAdapter | graph-storage, configuration, embedding | ✅ Healthy |
| server | FastAPI app, REST API, Database session | cli (via RemoteGraphStore) | PostgreSQLGraphStore, SearchService, AuthService, ServerDatabaseConfig | graph-storage, search, auth, configuration | ✅ Active |
| auth | AuthService, Auth middleware, Tenant/APIKey models, FakeAuthService | server | ConfigurationService | configuration | 🟡 Planned |
