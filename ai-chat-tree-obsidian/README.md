# AI Chat Tree - Obsidian Plugin

TypeScript Obsidian plugin that provides the UI layer for AI Chat Tree.

## Architecture

```
┌─────────────────────────────────────────────────────┐
│                  Obsidian App                        │
│  ┌─────────────┬─────────────────┬────────────────┐ │
│  │  Tree View  │   Chat Pane     │  Right Panel   │ │
│  │  (Sidebar)  │   (Center)      │  (Properties)  │ │
│  └─────────────┴────────┬────────┴────────────────┘ │
│                         │                            │
│  ┌──────────────────────┴──────────────────────────┐ │
│  │            Plugin Core (TypeScript)             │ │
│  └──────────────────────┬──────────────────────────┘ │
└────────────────────────┼────────────────────────────┘
                         │ HTTP
                         ▼
┌─────────────────────────────────────────────────────┐
│              AI Chat Tree Engine                     │
│           (localhost:8765 by default)               │
└─────────────────────────────────────────────────────┘
```

## Features

- **Family Tree Sidebar**: Browse Trunk → Branch → Turn hierarchy
- **Chat Pane**: Read turns and compose new prompts
- **Right Panel**: Turn properties, backlinks, fruits
- **Command Palette**: New turn, new branch, run RLM, etc.

## Status

Phase 0 (Design) complete. Implementation not yet started.

## Requirements

- Obsidian app (desktop or mobile)
- AI Chat Tree Engine running on localhost:8765 (or configurable endpoint)

## Development

```bash
cd ai-chat-tree-obsidian
npm install
npm run dev    # Build with watch
npm run build  # Production build
```