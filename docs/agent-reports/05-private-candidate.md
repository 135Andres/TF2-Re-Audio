# T19: verified private candidate — 2026-10-15

## Result and source identity

- Candidate: `dist/TF2ReAudio-0.1.0.zip` (local only).
- SHA-256: `60c105c1631860e1e516bd524282fd552c9f3a7ffac22b6a6c0fdd954d01ff33`.
- Size: 79,252 bytes; 35 archive entries.
- Source commit: `b7f9f3b330d8caae743b8e1e93964c8cfea5cd0c` plus the uncommitted working tree below.
- Environment: Linux, Python 3.14.8. Existing Playwright 1.62.1 and Chromium
  156.0.8078.4; no dependencies installed or downloaded.

```text
 M AUDITORIA_UX.md
 M docs/README.md
 M docs/local-ui-review.md
 M docs/milestone-wave2.md
 M tests/test_store.py
 M tests/test_web.py
 M tf2reaudio/store.py
 M tf2reaudio/web/app.js
?? docs/agent-reports/
?? docs/linux-real-session-2026-10-15.md
?? docs/superpowers/
```

The T8 and T15 changes and their reports were already present. Their final
integrated checkout passed the fresh full browser suite below. No other agent
was dispatched and no implementation file was modified by T19. Hashes of all
packaged inputs were unchanged across the two final builds. Each archive entry
was compared byte-for-byte with its corresponding source file.

## Changes

Read the distribution README first, then the project and local-closure plans.
Kept the existing working builder and its two tests unchanged. Updated
`docs/README.md` to identify the private candidate explicitly. Updated
`docs/local-ui-review.md` to separate historical checks from current evidence,
record limitations and remove the obsolete instruction to publish. Only those
T19 documents, this report and the generated ZIP were changed by this task.

Ruling: followed the assignment's single-agent, shared-checkout scope and used
this report as the execution record. No worktree or branch was created because
this packages the integrated dirty snapshot, and no implementation change or
commit was requested. Cost if wrong: concurrent writes could invalidate source
identity; input hashes, exact archive-byte comparison and repeat-build equality
were checked to detect that condition. Existing unrelated work was preserved.

## Commands and fresh results

1. `python -m unittest`: 198 tests in 23.035 s, OK, 9 skipped. Seven skips
   were optional browser checks; two were optional real tunnel/network checks.
2. Full browser run:

   ```sh
   TF2RA_PLAYWRIGHT=~/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright \
   TF2RA_BROWSER=~/.cache/ms-playwright/chromium-1248/chrome-linux64/chrome \
   python -m unittest
   ```

   198 tests in 57.129 s, OK, 2 skipped (optional real tunnel/network checks).
   All seven browser checks ran. The deliberate duplicate-entry ZIP fixture
   emitted its existing UserWarning. No real TF2 or external network was used.
3. `python -m unittest tests.test_build_zip -v`: 2 tests, OK, no skips.
4. `python tools/build_zip.py` twice, with the first ZIP saved in a temporary
   directory through `atomic_write`: identical bytes and identical SHA-256
   shown above. `ZipFile.testzip()` returned None. Exact allowlisted entries,
   safe relative paths, local web assets, Linux launcher mode 0755, source-byte
   equality and absence of data, caches, runtimes, agent work orders/reports and
   the local RCON password bytes were checked without printing secrets.
5. Extracted the final ZIP into a temporary path with spaces; checked
   `python -m tf2reaudio --version`, `python -m tf2reaudio run --help`, and
   `tf2reaudio.sh --version` from another working directory: all passed.
   The shell launcher mode was restored from ZIP metadata because Python's
   `extractall` does not restore executable bits; README documents `chmod +x`.
6. Final extracted smoke harness:

   ```sh
   python -c "exec(compile(open('/tmp/tf2ra-private-smoke.py', encoding='utf-8', newline='').read(), '/tmp/tf2ra-private-smoke.py', 'exec'))"
   ```

   This session-local harness reuses `make_vpk`, `wav` and `FakeRcon` helpers;
   it is not a project dependency. The child process imports the extracted
   package and asserts its module path, uses temporary app data and explicit
   fake TF2 paths, and patches Steam discovery to return no installations.
   Import installed three MEDIC! variants with exact fixture bytes. Apply
   reached fake RCON and sent `snd_restart`; `doctor --copy` reported connected
   without its fixture password. Restoring ORIGINAL removed all three files.
   A temporary loopback server on port 0 returned 200 and nonempty content for
   `/`, `/app.js`, `/recorder.js`, `/wav.js`, `/strings.js`, `/setup.js`,
   `/style.css`, `/api/ping`. All checks passed on the final archive.
   Initial harness execution used a password outside the application's allowed
   format, causing fixture authentication failure; after correcting the fixture
   to an accepted format, the full smoke passed, including a repeat on the
   final ZIP. No application fix was necessary.
7. `git diff --check`: passed.

The final ZIP was rebuilt after all packaged document edits, and the extracted
smoke was repeated afterward. This report is intentionally outside the ZIP;
adding its final checksum to a packaged file would change that checksum.

## Not run and requests to other tasks

Native Windows: Not run. Windows runtime bootstrap/download, sockets, file locks,
replacement and microphone permissions remain unverified. Physical microphones,
real TF2 playback, real RCON and mid-Casual reload duration: Not run. Firefox,
screen readers, full WCAG/keyboard acceptance and the five-person study: Not run.
The automated fixture checks do not complete either human milestone.

No cross-module implementation changes are required by this packaging work.
Assignments 03/04 can use the candidate path and checksum above for human Linux
and Windows validation. Assignment 06 owns updating `PLAN.md` and `TASKS.md`
with this fresh integrated result and the continuing human gates; those files
were not edited here. Keep collaboration deferred until the required milestones.
No upload, publication, release tag, merge, commit or license selection occurred.

## Packaged input SHA-256 manifest

This records every input included by the builder, including uncommitted inputs.

```text
ebdf26d77facea1a43c61ea2dd66b55446443f4a4db8abbabed31bd65782cb00  docs/README.md
d6be37ddca7553eecc651ef41cec3171403d1f9feff23a78a63ffb8fec52301e  TF2ReAudio.cmd
2f0d5d30b9f5e4b4712c69af11e867d63705a4bc03310c549d2d949969d32f81  docs/launchers.md
0046222a05910cef75093e4aa9c8da395d0bb1c1a153e55151277c1bb4d04014  docs/local-ui-review.md
a277f5703efc1f401957edaf6046c092c1805d1dcb5a7f46fde209ca687d12ee  docs/milestone-wave2.md
d8f397a3a386ef0412832fb5f2210010b9ea06f30ca3a3b4025d31f8f26533b2  tf2reaudio.sh
d3b0239d77911732248dcb768efd557de103fd1096a713bdaf089f43b3552ad7  tf2reaudio/__init__.py
5bab966df6900653764c82b0802891f6af33b426ff8839579dc14e95da705671  tf2reaudio/__main__.py
981f8a052f0f7f0b6c7360632c5778b1127b6014075a240524e8560f2cc6de61  tf2reaudio/audio.py
e6e33973b248ba845233c5b8e70a0f2de0746909c199040af17cd4ba6b4635b4  tf2reaudio/catalog.py
d8736a7543ccd8b0c1e6414e96ea195eb3160465ef09ce00588d64f09e55bfd8  tf2reaudio/game.py
772904515cd43b9807a275a717f8d36463f6f4eadfd1d4c70d50c471c8e8d054  tf2reaudio/rcon.py
27b4b3399eb783043cc429c62e9fba1b8de2821a6125e57a7ea578670b1c934f  tf2reaudio/server.py
95d9433b4bcd2e323ed4d26eabf86f322b5844ed4a4d2a797532182f958ff005  tf2reaudio/steam.py
497922e0f3aa0cf500281e988afffe8447a490f560817c0d96bd04ba0ad72219  tf2reaudio/store.py
7d3110506c4c5242ac24f6ec38a947bd1b23652e19aad52920f97e35030f88ed  tf2reaudio/tunnel.py
4ccc35094ec5f240cdd23813773800159810aa66f58f9dee4cc1109000da131b  tf2reaudio/util.py
831c0c9afae5d56753a77dd0a5270398a448ec4d606b56bed3e0e6ee5d797bf7  tf2reaudio/vpk.py
b7263b997ed8628304a4302358e9681520293728eb0d23a4a1069c819e632af9  tf2reaudio/web/app.js
69d571a23bdc0a9d63fb2c65b703a507721009fe5bf18e92952cf9567594cb19  tf2reaudio/web/favicon.svg
c57127d9f9bc1cda3270700ff7edbecee0bda348173055d904c1977dc2069da8  tf2reaudio/web/img/demoman.svg
9ae8a98650817368e098ef2b068d489371ee93e4998456cf10d33fe7d7b2e1ec  tf2reaudio/web/img/engineer.svg
d8e39912d2d9821abc0b81673764f881392eec95ca3acf38e28258e970c75ac9  tf2reaudio/web/img/heavy.svg
ffc394d06e23dc1eb8c68ee9746bb9b2cf5eddf7569ad5051957e6e72fbd03a0  tf2reaudio/web/img/medic.svg
2ca7376d8696ebcb0b6be7e135bb8d6fb16a6f0d2f224c693324a153787139fe  tf2reaudio/web/img/pyro.svg
df68ad7134c9e394202b80df2a2bc057d2cfe52791fdad2ee6d100824fbb1329  tf2reaudio/web/img/scout.svg
1a4bcb9af941797d67d682d0a5becb378cbd57b3684955f0cd6cb70d43c615e1  tf2reaudio/web/img/sniper.svg
383b514ea7f155c8044e62313e5338652d471d1fa293067a948b1026f9bb8406  tf2reaudio/web/img/soldier.svg
c05ee88ff10037e14deb391a3099f46e146b4362346a1c9be37db61106417bc5  tf2reaudio/web/img/spy.svg
26b333bcc92097d8fc38fd705f3c1f1d3e06688059853d243203bfa79110eb4c  tf2reaudio/web/index.html
d800084954ff45b55f3e868a67ad31c7edfb5bceac7eead0b7b43e46051da13f  tf2reaudio/web/recorder.js
b60fd7c70761c6f54f7ed9e6b28e2798ca47defa8c1d6e2528d3f4a302664e3b  tf2reaudio/web/setup.js
fd5fd43e939674c280e9571fd43f5ea97442a85ecb73c4bb6ec79cb102819e9f  tf2reaudio/web/strings.js
ed54827c1ae4442ad1feb35636957ee32456f3e81b6106e8a102686be69db3b3  tf2reaudio/web/style.css
93d1b7e2a26370fbaa491e0a33835c2ddce9468633a84784814e6faaf768eda9  tf2reaudio/web/wav.js
```
