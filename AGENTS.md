# VeloPath AI - Agent Instructions (Ponytail Active)

This project follows the **Ponytail** engineering standard: minimal, simplest, lazy-senior-dev code.

## The Decision Ladder

1. **YAGNI**: Speculative need = skip it.
2. **Codebase reuse**: Use helpers/patterns that already exist in `velopath/`.
3. **Standard Library**: Reach for Python stdlib (`os`, `sys`, `urllib`, `dataclasses`, `typing`, `math`) before custom code.
4. **Native Platform**: Use HTML5 video API, CSS styling, and browser primitives before heavy libraries.
5. **Installed Dependencies**: Use existing dependencies (`fastapi`, `numpy`, `scipy`, `cv2`, `ultralytics`). Never add new ones when existing libraries or stdlib can do the job.
6. **Fewest Lines**: One line over fifty. Boring over clever. Deletion over addition.
7. **Root Cause**: Fix bugs at the root cause, not symptoms. One guard in the shared function rather than patches across callers.

## Core Rules
- No unrequested abstractions or single-implementation interfaces.
- Preserve trust-boundary validation, physical simulation safety, and accurate mathematical proofs.
- Verify changes with `pytest tests/ -v`.
