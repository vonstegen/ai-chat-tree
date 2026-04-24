# Files & Fruits System

## Node File Structure

Each Turn node consists of:
- `Turn-XXX.md` → Main chat (prompt + AI response)
- `Turn-XXX-fruits/` → Attached rich outputs

### Fruit Types
- **Scripts**: `.ts`, `.py`, `.js`
- **Images**: `.png`, `.svg`
- **Terminal/Execution**: `execution-log.txt`, `output.json`
- **Diffs & Artifacts**: `changes.diff`, `preview.html`

## Linking
Use Obsidian wikilinks:
```markdown
![[Turn-042-fruits/premium-preview.png]]
[[Turn-042-fruits/dashboard-component.tsx|View Script]]