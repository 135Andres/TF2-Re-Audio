# Rules for all agents

Read `PLAN.md` and `TASKS.md` before any task. Each task in TASKS.md owns the files it lists; do not edit files owned by other tasks. If you need a change in another module, write it in your report.

- **Python >=3.10, standard library only.** No `pip install`.
- Must work on **Windows and Linux**: always use `pathlib`, never assume `/`, and set `newline`/`encoding="utf-8"` explicitly.
- Tests use `unittest` in `tests/test_<module>.py`. They run with `python -m unittest` from the repo root and must not touch the real TF2 or the network. Use fixtures and fake servers on `127.0.0.1` with port 0.
- All persistent data writes go through `util.atomic_write`.
- User-visible text: **in English**.
- Expected errors (missing file, network down, game closed) -> the module's own exceptions with a clear message. Never show a traceback to the user.
- When done, the report includes: what was done, how it was tested, what was not tested (especially Windows), and the changes you need from other tasks.
