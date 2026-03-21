---
name: Use conda for Python environments
description: User wants all Python installs in conda envs to protect local environment
type: feedback
---

Always use conda (Anaconda at C:\Users\hxin\anaconda3) to create isolated environments. Never pip install into the base/local Python environment.

**Why:** User wants to keep local environment clean and avoid dependency conflicts.

**How to apply:** When any Python package installation is needed, create or activate a conda env first. Use `C:\Users\hxin\anaconda3\Scripts\conda.exe` since conda is not on PATH by default.
