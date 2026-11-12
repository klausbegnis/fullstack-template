# Third-party notices

This repository is MIT-licensed (see `LICENSE`). It also vendors the following
third-party material, each under its own license kept next to it.

| Path | Source | License |
| --- | --- | --- |
| `.agents/skills/react-best-practices/` | [vercel-labs/agent-skills](https://github.com/vercel-labs/agent-skills) `skills/react-best-practices` @ `063bee94` | MIT, see `LICENSE` in that folder |

`.agents/skills/fastapi` is not vendored: it is a symlink to the skill that the
`fastapi` package ships inside its wheel, and resolves once `uv sync` has created
`backend/.venv`. It is covered by FastAPI's own MIT license.
