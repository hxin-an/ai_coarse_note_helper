---
name: context_compression_strategy
description: When and how to compress context to save token usage in long note-generation sessions
type: feedback
---

After completing a note (completeness check ✅ + commit + push), start a new chat session rather than continuing in the same context.

**Why:** Reading 40+ slide images consumes significant context. After a note is done, the context is no longer needed and just wastes tokens.

**How to apply:**
- Trigger: one full note cycle done (slides read → note written → committed → pushed)
- Action: inform user that context is now large and suggest opening a new chat
- In the new chat: read NOTES_STATUS.md + CLAUDE.md to restore state — no need for user to re-explain anything
