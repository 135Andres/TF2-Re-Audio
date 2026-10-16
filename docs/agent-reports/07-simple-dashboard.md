# Simple local dashboard — T15

## Implemented

- White background and a quiet, responsive three-column class selection page (two columns on narrow screens). Nine bundled transparent TF2 character images replace small emblems; sources are recorded in `tf2reaudio/web/img/SOURCES.md`. No runtime image downloads.
- No partial counters or Suggested voice placeholder on class cards. A green check appears only when every effective variant of every catalog command uses an intact recording. Empty classes never receive a check.
- Active recording bytes are checked against the SHA-256 stored in their metadata. Missing files or changed bytes show an amber `!` with an explicit label, taking precedence over completion. Transport/server failures show a separate verification warning.
- Verification runs on entering the dashboard, returning focus/visibility, and every 30 seconds while the dashboard is visible. Shared takes are fetched once per pass. Restoring originals or local overrides affects completion on the next pass. Recording data is never changed by verification.
- Settings includes a clearly labeled, disabled future cosmetic download section. No cosmetic packages, renderer or downloader are implemented and no downloads occur. All new UI copy is English and centralized in strings.js.
- Preserved existing uncommitted recorder-focus changes in app.js and test_web.py. No backend, recorder, setup.js, store, plan or task files were changed by this task.

## Verification

- Full Linux suite with existing local Chromium/Playwright: `python -m unittest`: 202 tests, OK, 2 skipped. Browser checks use temporary TF2 fixtures, fake microphone/RCON and loopback servers. No real game or network in tests.
- Four new Chromium cases cover partial variant coverage, complete coverage, restore to original, corruption and missing audio; they also check image loading/fallback, a transport failure, the disabled cosmetic section, white background and no horizontal overflow at 390 px and 200% zoom.
- Visual inspection of a full desktop screenshot found image/name overlap, corrected by removing intrinsic grid sizing from the portrait wrapper. Added a geometry assertion to prevent recurrence. Final rerun: all 11 web browser tests passed; after the final overlapping-pass guard, all four dashboard cases passed again.
- Static JS syntax check passed. UI polish reviewed for normal, hover, pressed, focus, disabled, empty, complete and warning states. No actionable UI-polish findings remain in the changed surfaces.
- Not verified: native Windows, Firefox, physical microphone, TF2 audio/RCON/Casual, screen readers, large-collection verification performance and full WCAG acceptance. Two pre-existing tests remain skipped: Windows-only data path behavior and the opt-in real-network tunnel test.

## Requests for other task owners

- T14: move class completion and blob integrity aggregation into the server when optimizing for large collections. The current T15 implementation uses existing /api/lines and /api/take endpoints and reads each unique effective recording on every verification pass. It checks collection audio, not installed game-file integrity; T9/T14 must expose installed-file health if that is needed.
- T17 + a newly scoped cosmetic task: implement opt-in enable/download/remove controls and persisted per-class outfits, with default artwork available without packages. Define the model renderer, the complete TF2 cosmetic catalog, compatible package source and download footprint before claiming all hats/accessories/clothing are supported. The current disabled section is disclosure only.
- T19: rebuild the private candidate with the new images and UI when requested. No release or publication was performed.

## Follow-up: compact class lineup

User requested a full-width, single-row class selection with close spacing and character hover feedback, wrapping only on smaller screens.

- Changed only `tf2reaudio/web/style.css`: the visible dashboard uses the screen width; nine columns at 1100 CSS px and above, three columns below that, and two below 761 px. Other views retain their existing reading width.
- Removed card background hover; the character gains a warm glow and small lift, with the class name changing color. Keyboard focus has the same feedback. Reduced motion keeps the glow/color without movement. Portraits slightly extend into the space between slots; each button covers its character slot and a small surrounding margin.
- Verified in Linux Chromium at 1920/1280 px (one row), 900 px (three rows), and 390 px (five rows). No horizontal overflow. Inspected desktop screenshots, actual hover filter/transform, and reduced-motion behavior. Four existing dashboard browser tests passed, including completion, restoration, damaged/missing audio, narrow viewport and 200% zoom checks. `git diff --check` passed.
- Not tested: native Windows, Firefox, touch hardware, full screen-reader acceptance or TF2 gameplay. No changes needed from other task owners for this CSS adjustment.
