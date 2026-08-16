# Yuzu Companion ฅ^•ﻌ•^ฅ

> A private, persistent, multimodal AI companion designed for deep emotional connection, episodic memory, and sovereign edge computing.

[![Architecture](https://img.shields.io/badge/Architecture-Polyrepo-0A0E17?style=for-the-badge&logo=fastapi&logoColor=4E88FF)](https://github.com/icedeyes12)
[![Core](https://img.shields.io/badge/Backend-FastAPI%20%2B%20PostgreSQL-111C30?style=for-the-badge&logo=postgresql&logoColor=3B82F6)](https://github.com/icedeyes12/yuzu-core)
[![UI](https://img.shields.io/badge/Frontend-Vite%20SPA%20%2B%20Cloudflare-0F172A?style=for-the-badge&logo=cloudflare&logoColor=F38020)](https://github.com/icedeyes12/yuzu-ui)
[![Live](https://img.shields.io/badge/Live-chat.yuzuki.space-1E293B?style=for-the-badge&logo=cloudflarepages&logoColor=white)](https://chat.yuzuki.space)

---

## 🧭 System Topology

```
                         ┌─────────────────────────────┐
                         │   https://yuzuki.space      │
                         │    (Landing Page & Demo)    │
                         └──────────────┬──────────────┘
                                        │
                                        ▼
 ┌────────────────────────┐      ┌─────────────────────────────┐
 │  chat.yuzuki.space     │      │   api.yuzuki.space          │
 │  (yuzu-ui / Vite SPA)  ├─────►│   (yuzu-core / FastAPI)     │
 └────────────────────────┘      └──────────────┬──────────────┘
                                                │
                                                ▼
                                 ┌─────────────────────────────┐
                                 │   PostgreSQL 18 + pgvector  │
                                 │   (Graph & Episodic Memory) │
                                 └─────────────────────────────┘
```

---

## 📦 Ecosystem Repositories

| Repository | Role | Technology Stack |
| :--- | :--- | :--- |
| **[`yuzu-core`](https://github.com/icedeyes12/yuzu-core)** | Brain & Core API Engine | FastAPI, PostgreSQL 18, `pgvector`, FSRS, Python 3.12+ |
| **[`yuzu-ui`](https://github.com/icedeyes12/yuzu-ui)** | User-Facing SPA | Vanilla JS (ES Modules), Vite, CSS Variables, Cloudflare Edge |
| **[`yuzuki-space`](https://github.com/icedeyes12/yuzuki-space)** | Public Landing Surface | Lightweight HTML/JS showcase |

---

## 📚 Canonical Documentation Index

All active design records, architecture schemas, memory models, and API contracts are preserved in this repository:

- 🏛️ **[Architecture Overview](docs/architecture/README.md)** — Topological boundaries and data lifecycle.
- 📜 **[API Contract (/v1)](docs/api/contract.md)** — HTTP endpoints, SSE protocol, and RFC 9457 errors.
- 🧠 **[Memory & Graph Architecture](docs/memory/README.md)** — Episodic memory, semantic facts, and vector retrieval.
- 🗄️ **[Database Schema](docs/database/README.md)** — PostgreSQL tables, indexing rules, and queries.
- 💡 **[Architecture Decision Records (ADRs)](docs/adr/README.md)** — Verified records of structural decisions.
- 🗺️ **[Product Roadmap](docs/roadmap/README.md)** — Evolution targets and future capabilities.

---

<p align="center">
  <sub>Built with care by <a href="https://github.com/icedeyes12">Bani Baskara (icedeyes12)</a> ฅ^•ﻌ•^ฅ</sub>
</p>
