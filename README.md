# AI Chat Tree 🌳

> An Obsidian-native, node-centric, branching AI conversation system with **Guardian** (pi-infra) enforcement.

Guardian is the deterministic policy enforcement layer from `packages/guardian/` in pi-infra. All mutations pass through it as the gate.

---

## Architecture Overview

- **Tree Engine** — Python/FastAPI (`localhost:8765`). `ai-chat-tree-engine/`
- **Obsidian Plugin** — TypeScript plugin (scaffold present, functional implementation pending)
- **Guardian** — TypeScript deterministic rule engine from [pi-infra/packages/guardian/][pi-guardian]. Verdicts: ALLOW / HOLD / DENY. All turns, branches, and fruits gated by Guardian.
- **Bridge Hook** — `~/.hermes/hooks/tree-node/handler.py`. Two-tier: agent:step (real-time, low-fidelity) + session:end (canonical, full fidelity)

[pi-guardian]: https://github.com/vonstegen/pi-infra/tree/main/packages/guardian

---

## Core Data Model

```
Trunko (root of conversation hierarchy)
  └── Brancho (conversation/thread)
        └── Turno (atomic Turn → prompt + response)
              └── Fruito (additional outputs attached to a turn)
```

### Turno Schema (v1.0)
- Required: `id`, `timestamp`, `branch`, `parent_turn`, `model`, `success_score`, `tags`, `guardian_hash`
- Optional: `revision_of`, `revision_number`, `change_reason`, `source`

---

## Project Status

- Architecture & RLM design: ✅ complete
- Bridge Architecture: ✅ complete — engine running, hook wired
- Guardian integration architecture: ✅ defined ([PROPOSED-GUARDIAN-INTEGRATION.md][guardian-doc])
- Guardian engine implementation: ⏳ pending (see [guardian-doc][guardian-doc])
- Obsidian plugin scaffold: ✅ present (not yet functional)
- Vector store: ✅ exists (not yet integrated)

[guardian-doc]: ./docs/PROPOSED-GUARDIAN-INTEGRATION.md

---

## Documentation

- [Guardian Integration Proposal][guardian-doc]
- [Bridge Architecture](./docs/bridge-architecture.md)
- [Master Checklist](./MASTER-Checklist.md)
- [Architecture](./docs/architecture.md)
- [Memory System](./docs/memory.md)

---

**Let's build the future of structured AI conversation.**

*Last updated: 2026-07-24 by VIGIL*
*Last updated: 2026-06-22 by VIGIL*
