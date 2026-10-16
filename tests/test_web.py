"""Optional browser acceptance checks against temporary TF2 fixtures only.

Run with TF2RA_PLAYWRIGHT pointing to an existing Playwright Node package and
TF2RA_BROWSER pointing to an existing Chromium executable. No downloads or
Python dependencies are needed; these checks are skipped when not configured.
"""
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from tests.fixtures.make_vpk import make_vpk
from tests.test_store import wav
from tf2reaudio.rcon import RconNotRunning
from tf2reaudio.server import LocalApp, LocalServer
from tf2reaudio.store import Store
from tf2reaudio.util import atomic_write


PLAYWRIGHT = os.environ.get("TF2RA_PLAYWRIGHT")
BROWSER = os.environ.get("TF2RA_BROWSER")


@unittest.skipUnless(PLAYWRIGHT and BROWSER and shutil.which("node"), "Optional local Chromium acceptance checks")
class WebTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        root = Path(self.tmp.name)
        tf = root / "Team Fortress 2" / "tf"
        tf.mkdir(parents=True)
        atomic_write(tf / "gameinfo.txt", b"fixture")
        names = {f"sound/vo/soldier_medic{i:02}.mp3": wav() for i in range(1, 4)}
        names.update({"sound/vo/soldier_thanks01.mp3": wav(), "sound/vo/soldier_jeers01.mp3": wav()})
        make_vpk(tf / "tf2_sound_vo_english_dir.vpk", names)
        for name, value in [("tf2reaudio.steam.find_installs", []), ("tf2reaudio.game.rcon.send", None)]:
            kwargs = {"return_value": value} if value is not None else {"side_effect": RconNotRunning("Game closed.")}
            mocked = patch(name, **kwargs)
            mocked.start()
            self.addCleanup(mocked.stop)
        self.app = LocalApp(tf, root / "data")
        self.server = LocalServer(self.app, port=0).start()
        self.addCleanup(self.server.stop)
        self.root = root

    def browser(self, case):
        env = dict(os.environ, TF2RA_URL=self.server.url, TF2RA_CASE=case, TF2RA_TEMP=str(self.root))
        result = subprocess.run(["node", "-e", BROWSER_CHECKS], cwd=Path(__file__).resolve().parent.parent,
                                env=env, capture_output=True, encoding="utf-8", timeout=90)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def seed_dashboard(self, complete=False):
        ids = ["soldier/medic", "soldier/thanks", "soldier/jeers"] if complete else ["soldier/medic#02"]
        for line_id in ids:
            take = self.app.game.store.add_take(line_id, wav(), "local")
            self.app.game.store.set_active(line_id, take)
        return self.app.game.store.history(ids[0])[0]["sha256"]

    def test_dashboard_hides_empty_and_partial_progress(self):
        self.seed_dashboard()
        self.browser("dashboard-partial")

    def test_dashboard_marks_only_all_variants_complete_and_restores(self):
        self.seed_dashboard(complete=True)
        self.browser("dashboard-complete")

    def test_dashboard_warns_when_saved_audio_is_corrupt(self):
        sha = self.seed_dashboard(complete=True)
        atomic_write(self.app.game.store.root / "blobs" / (sha + ".wav"), b"damaged audio")
        self.browser("dashboard-damaged")

    def test_dashboard_warns_when_saved_audio_is_missing(self):
        sha = self.seed_dashboard(complete=True)
        (self.app.game.store.root / "blobs" / (sha + ".wav")).unlink()
        self.browser("dashboard-damaged")

    def test_microphone_lifecycle_and_limit(self):
        self.browser("microphone")
        takes = self.app.game.store.history("soldier/medic")
        self.assertEqual(len(takes), 1)
        from tf2reaudio.audio import inspect_wav
        info = inspect_wav(self.app.game.store.blob(takes[0]["sha256"]))
        self.assertLessEqual(info.duration_s, 10)

    def test_browser_policy_blocks_inline_scripts_and_allows_audio(self):
        self.browser("csp")

    def test_collection_recovery_backup_and_settings(self):
        take = self.app.game.store.add_take("soldier/medic", wav(), "local")
        self.app.game.store.set_active("soldier/medic", take)
        self.app.sync_files()
        test_mod = self.app.game.tf / "custom" / "tf2reaudio_test"
        test_mod.mkdir()
        atomic_write(test_mod / "fixture.txt", b"test mod")
        self.browser("collection")
        self.assertEqual(len(self.app.game.store.history("soldier/medic")), 1)
        self.assertEqual(self.app.game.settings["rcon_port"], 28015)
        self.assertFalse(self.app.game.mod.exists())
        self.assertFalse(test_mod.exists())

    def test_variant_recording_and_keyboard_zoom(self):
        self.browser("variant")
        self.assertIsNone(self.app.game.store.active("soldier/medic"))
        self.assertIsNotNone(self.app.game.store.active("soldier/medic#02"))
        self.assertFalse((self.app.game.mod / "sound" / "vo" / "soldier_medic01.mp3").exists())
        self.assertTrue((self.app.game.mod / "sound" / "vo" / "soldier_medic02.mp3").exists())

    def test_recorder_focus_cancel_failure_and_whole_line(self):
        self.browser("recorder-focus")
        self.assertEqual(len(self.app.game.store.history("soldier/medic")), 1)
        self.assertEqual(self.app.game.store.history("soldier/medic#02"), [])

    def test_conflicts_keep_both_takes_and_resolve_from_history(self):
        other = Store(self.root / "other", "second-device", catalog=self.app.catalog)
        for store, frequency in [(self.app.game.store, 440), (other, 880)]:
            take = store.add_take("soldier/medic", wav(frequency), "local")
            store.set_active("soldier/medic", take)
        self.app.game.store.merge(other.snapshot())
        for sha in self.app.game.store.missing_blobs():
            self.app.game.store.put_blob(other.blob(sha))
        self.app.sync_files()
        self.browser("conflict")
        self.assertEqual(self.app.game.store.conflicts(), [])
        self.assertEqual(len(self.app.game.store.history("soldier/medic")), 2)

    def test_first_use_recovers_from_wrong_folder(self):
        tf = self.app.tf_dir
        self.server.stop()
        self.app = LocalApp(root=self.root / "fresh")
        self.server = LocalServer(self.app, port=0).start()
        self.addCleanup(self.server.stop)
        self.browser("setup")
        self.assertEqual(self.app.tf_dir, tf)


BROWSER_CHECKS = r"""
const assert = require('node:assert/strict');
const {chromium} = require(process.env.TF2RA_PLAYWRIGHT);
const path = require('node:path');
(async () => {
  const browser = await chromium.launch({headless:true, executablePath:process.env.TF2RA_BROWSER,
    args:['--no-sandbox','--disable-background-networking','--use-fake-device-for-media-stream','--use-fake-ui-for-media-stream']});
  try {
    const context = await browser.newContext({acceptDownloads:true, viewport:{width:1280,height:900}});
    await context.route('**/*', route => new URL(route.request().url()).origin === process.env.TF2RA_URL ? route.continue() : route.abort());
    const page = await context.newPage();
    const errors = [];
    page.on('pageerror', error => errors.push(error.message));
    await page.addInitScript(() => {
      window.capturedTracks = [];
      const get = navigator.mediaDevices.getUserMedia.bind(navigator.mediaDevices);
      navigator.mediaDevices.getUserMedia = async (...args) => {
        const stream = await get(...args);
        capturedTracks.push(...stream.getTracks());
        return stream;
      };
    });
    const expectVisible = async locator => {
      await locator.waitFor({state:'visible'});
      assert(await locator.isVisible());
    };
    const medic = () => page.locator('article[data-line-id="soldier/medic"]');
    // Secondary line actions sit in the line's own disclosure, apart from variant rows.
    const more = () => medic().locator('details.line-details > .recovery-actions');
    const click = (holder, text) => holder.getByRole('button',{name:text,exact:true}).click();
    const tracksEnded = async () => {
      await page.waitForFunction(() => capturedTracks.length > 0 && capturedTracks.every(track => track.readyState === 'ended'));
    };
    await page.goto(process.env.TF2RA_URL);
    const dashboardCase = process.env.TF2RA_CASE.startsWith('dashboard-');
    if (dashboardCase) {
      const soldier = page.locator('.class-card[data-class-id="soldier"]');
      const card = id => page.locator(`.class-card[data-class-id="${id}"]`);
      await expectVisible(soldier);
      assert.equal(await page.locator('.class-card').count(), 9);
      assert.equal(await page.evaluate(() => getComputedStyle(document.body).backgroundColor), 'rgb(244, 239, 230)');
      await page.waitForFunction(() => [...document.querySelectorAll('.class-card')].every(el => el.dataset.audioStatus));
      assert.equal(await card('scout').getAttribute('data-audio-status'), 'partial');
      assert.equal(await card('scout').locator('.class-badge').isVisible(), false);
      for (const image of await page.locator('.class-portrait img').all()) {
        assert(await image.evaluate(async img => {
          await img.decode();
          const artwork = img.getBoundingClientRect();
          const label = img.closest('.class-card').querySelector('.class-name').getBoundingClientRect();
          return img.naturalWidth > 0 && artwork.bottom <= label.top;
        }));
      }
      assert.equal(await soldier.locator('.class-progress').count(), 0);
      if (process.env.TF2RA_CASE === 'dashboard-partial') {
        assert.equal(await soldier.getAttribute('data-audio-status'), 'partial');
        assert.equal(await soldier.locator('.class-badge').isVisible(), false);
        // A transport failure must not be reported as corruption or completion.
        await page.route('**/api/lines?class=soldier', route => route.abort());
        await page.evaluate(() => window.dispatchEvent(new Event('focus')));
        await page.waitForFunction(() => document.querySelector('[data-class-id="soldier"]').dataset.audioStatus === 'unchecked');
        assert.match(await soldier.innerText(), /Could not check recordings/);
        await page.unroute('**/api/lines?class=soldier');
      } else if (process.env.TF2RA_CASE === 'dashboard-complete') {
        assert.equal(await soldier.getAttribute('data-audio-status'), 'complete');
        assert.match(await soldier.innerText(), /✓.*All voices replaced/s);
        await soldier.click();
        await medic().locator('summary').click();
        await click(more(), 'Restore original for this collection');
        await click(page, '← All classes');
        await page.waitForFunction(() => document.querySelector('[data-class-id="soldier"]').dataset.audioStatus === 'partial');
        assert.equal(await soldier.locator('.class-badge').isVisible(), false);
      } else {
        assert.equal(await soldier.getAttribute('data-audio-status'), 'damaged');
        assert.match(await soldier.innerText(), /!.*Recording missing or damaged/s);
        assert.equal(await soldier.locator('.class-badge').evaluate(el => getComputedStyle(el).backgroundColor), 'rgb(255, 241, 184)');
      }
      // Failed artwork still leaves a named, usable class button.
      await page.route('**/img/scout.png*', route => route.abort());
      await card('scout').locator('img').evaluate(img => { img.src += '?missing'; });
      await expectVisible(card('scout').locator('.class-portrait > span'));
      await click(page, 'Setup & settings');
      await expectVisible(page.getByRole('heading', {name:'Setup & settings'}));
      await click(page, '← Back');
      await page.setViewportSize({width:390, height:844});
      assert(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth));
      await page.setViewportSize({width:640, height:900});
      await page.evaluate(() => { document.documentElement.style.zoom = '2'; });
      assert(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth));
    }
    if (process.env.TF2RA_CASE !== 'setup' && !dashboardCase) await page.getByRole('button',{name:/Soldier/}).click();

    if (process.env.TF2RA_CASE === 'microphone') {
      await click(page, 'Start with MEDIC!');
      await click(page, 'Start recording');
      await page.waitForFunction(() => capturedTracks.some(track => track.readyState === 'live'));
      await page.keyboard.press('Escape');
      await tracksEnded();
      assert.equal(await page.locator('#recorder-dialog').isVisible(), false);
      // Closing while the browser permission request is unresolved also stops late tracks.
      await page.evaluate(() => {
        const get = navigator.mediaDevices.getUserMedia;
        navigator.mediaDevices.getUserMedia = async (...args) => {
          await new Promise(resolve => setTimeout(resolve, 300));
          return get(...args);
        };
      });
      await click(page, 'Start with MEDIC!');
      await click(page, 'Start recording');
      await page.keyboard.press('Escape');
      await page.waitForTimeout(700);
      await tracksEnded();
      await click(page, 'Start with MEDIC!');
      // Simulate a background tab: visual animation cannot enforce the limit.
      await page.evaluate(() => { window.requestAnimationFrame = () => 0; });
      await click(page, 'Start recording');
      await expectVisible(page.getByRole('button',{name:'Save recording',exact:true}));
      await tracksEnded();
      await click(page, 'Save recording');
      await expectVisible(page.locator('#notice'));
      await page.waitForFunction(() => !document.querySelector('#recorder-dialog').open);
      await click(page, 'Continue recording');
      await page.evaluate(() => {
        navigator.mediaDevices.getUserMedia = async () => { throw new DOMException('blocked','NotAllowedError'); };
      });
      await click(page, 'Start recording');
      await expectVisible(page.getByText('Microphone permission is blocked.',{exact:false}));
      await page.keyboard.press('Escape');
      await tracksEnded();
    } else if (process.env.TF2RA_CASE === 'collection') {
      await click(page, 'I restarted TF2');
      await page.waitForFunction(() => document.querySelector('#restart-notice').hidden);
      page.once('dialog', dialog => dialog.accept());
      await click(page, 'Remove tf2reaudio_test');
      await page.waitForFunction(() => document.querySelector('#test-mod-notice').hidden);
      await medic().locator('summary').click();
      await click(more(), 'Use original on my PC only');
      await expectVisible(medic().getByText('Original on this PC only', {exact:false}));
      await click(more(), 'Use collection voice on my PC');
      await click(more(), 'Restore original for this collection');
      await expectVisible(medic().getByText('Using the original', {exact:false}));
      await click(more(), 'Undo last change');
      await click(more(), 'History');
      await expectVisible(page.locator('#history-dialog .player-toggle').first());
      await click(page.locator('#history-dialog'), 'Use this recording');
      await page.waitForFunction(() => !document.querySelector('#history-dialog').open);
      await click(page, '← All classes');
      await click(page, 'Setup & settings');
      await page.locator('#rcon-port').fill('28015');
      await click(page, 'Save port');
      await click(page, 'Copy launch options');
      await expectVisible(page.locator('#launch-options'));
      assert.match(await page.locator('#launch-options').inputValue(), /hostport 28015/);
      const pendingDownload = page.waitForEvent('download');
      await click(page, 'Export collection');
      const download = await pendingDownload;
      const backup = path.join(process.env.TF2RA_TEMP, 'backup.zip');
      await download.saveAs(backup);
      // Cancellation must not delete anything.
      page.once('dialog', dialog => dialog.dismiss());
      await click(page, 'Delete collection');
      const before = await page.request.get(process.env.TF2RA_URL + '/api/history?line_id=soldier%2Fmedic');
      assert.equal((await before.json()).takes.length, 1);
      page.once('dialog', dialog => dialog.accept());
      await click(page, 'Disable voices');
      await expectVisible(page.locator('#enable-voices'));
      await click(page, 'Enable voices');
      page.once('dialog', dialog => dialog.accept());
      await click(page, 'Delete collection');
      await page.locator('#import-file').setInputFiles(backup);
      await click(page, 'Import collection ZIP');
      await expectVisible(page.getByText('Collection imported.',{exact:false}));
      page.once('dialog', dialog => dialog.accept());
      await click(page, 'Uninstall');
      await expectVisible(page.locator('#uninstall-guide'));
      assert.match(await page.locator('#remove-options').inputValue(), /hostport 28015/);
    } else if (process.env.TF2RA_CASE === 'recorder-focus') {
      const record = async () => {
        await click(page, 'Start recording');
        await page.waitForTimeout(600);
        await click(page, 'Stop');
        await expectVisible(page.getByRole('button',{name:'Save recording',exact:true}));
        await tracksEnded();
      };
      const focused = async locator => {
        // The native dialog close event is queued after its open flag changes.
        await page.waitForFunction(el => el === document.activeElement,
          await locator.elementHandle(), {timeout:3000}).catch(async error => {
            throw new Error(`${error.message}; active=${await page.evaluate(() => document.activeElement.outerHTML.slice(0, 200))}`);
          });
        assert(await locator.evaluate(el => el.isConnected && el.getClientRects().length > 0));
      };
      await medic().locator('summary').click();
      const row = medic().locator('[data-line-id="soldier/medic#02"]');
      await click(row, 'Record voice');
      await page.keyboard.press('Escape');
      await page.waitForFunction(() => !document.querySelector('#recorder-dialog').open);
      await focused(row.getByRole('button',{name:'Record voice',exact:true}));
      await click(row, 'Record voice');
      await record();
      // Details may close while the modal is open; return to a visible line control.
      await medic().locator('details').evaluate(el => { el.open = false; });
      await click(page, 'Discard');
      await page.waitForFunction(() => !document.querySelector('#recorder-dialog').open);
      await focused(medic().getByRole('button',{name:'Record voice',exact:true}).first());
      await click(medic(), 'Record voice');
      await record();
      await page.route('**/api/take', route => route.fulfill({status:500,
        contentType:'application/json',body:JSON.stringify({error:'Save failed for focus test.'})}));
      await click(page, 'Save recording');
      await expectVisible(page.getByText('Save failed for focus test.',{exact:true}));
      assert(await page.locator('#recorder-dialog').evaluate(el => el.open && el.contains(document.activeElement)));
      assert(await page.getByRole('button',{name:'Save recording',exact:true}).isEnabled());
      assert(await page.locator('#take-preview').evaluate(el => Boolean(el.src)));
      await page.unroute('**/api/take');
      await click(page, 'Save recording');
      await page.waitForFunction(() => !document.querySelector('#recorder-dialog').open);
      await expectVisible(medic().getByRole('button',{name:'Record again',exact:true}));
      await focused(medic().getByRole('button',{name:'Record again',exact:true}));
      await page.keyboard.press('Tab');
      await focused(medic().getByRole('button',{name:'Play recording',exact:true}));
    } else if (process.env.TF2RA_CASE === 'variant') {
      await page.getByRole('tab',{name:'Voice menu',exact:true}).focus();
      await page.keyboard.press('End');
      assert.equal(await page.getByRole('tab',{name:'All lines',exact:true}).getAttribute('aria-selected'),'true');
      await page.waitForFunction(() => document.querySelectorAll('#line-list article').length >= 3);
      await page.getByRole('tab',{name:'Voice menu',exact:true}).click();
      await medic().locator('summary').click();
      const row = medic().locator('[data-line-id="soldier/medic#02"]');
      await click(row, 'Record voice');
      assert.match(await page.locator('#recorder-line').textContent(), /Variant 02.*1 game file/);
      await click(page, 'Start recording');
      await page.waitForTimeout(600);
      await click(page, 'Stop');
      await expectVisible(page.getByRole('button',{name:'Save recording',exact:true}));
      await tracksEnded();
      await click(page, 'Save recording');
      await page.waitForFunction(() => !document.querySelector('#recorder-dialog').open);
      await expectVisible(row.getByRole('button',{name:'Record again',exact:true}));
      assert(await row.getByRole('button',{name:'Record again',exact:true}).evaluate(el =>
        el === document.activeElement && el.isConnected && el.getClientRects().length > 0),
        await page.evaluate(() => `Focus after variant save: ${document.activeElement.outerHTML.slice(0, 200)}`));
      await page.evaluate(() => { document.documentElement.style.zoom = '2'; });
      await page.setViewportSize({width:1000,height:900});
      await page.keyboard.press('Tab');
      assert(await page.evaluate(() => document.activeElement !== document.body));
      assert(await page.evaluate(() => {
        const el = document.activeElement;
        return el.matches('button, input, select, summary, a[href]') && !el.disabled && el.getClientRects().length > 0;
      }));
      assert(await page.evaluate(() => document.documentElement.scrollWidth <= document.documentElement.clientWidth));
    } else if (process.env.TF2RA_CASE === 'conflict') {
      await expectVisible(medic().getByText('Conflicting recordings',{exact:false}));
      await medic().locator('summary').click();
      await click(more(), 'History');
      await expectVisible(page.locator('#history-dialog'));
      assert.equal(await page.locator('#history-dialog audio').count(), 2);
      await page.getByRole('button',{name:'Use this recording & resolve conflict',exact:true}).first().click();
      await page.waitForFunction(() => !document.querySelector('#history-dialog').open);
    } else if (process.env.TF2RA_CASE === 'csp') {
      await page.evaluate(() => {
        window.policyViolations = [];
        document.addEventListener('securitypolicyviolation', event => policyViolations.push(event.effectiveDirective));
        const script = document.createElement('script');
        script.textContent = 'window.untrustedInlineRan = true;';
        document.head.append(script);
      });
      assert.equal(await page.evaluate(() => window.untrustedInlineRan), undefined);
      await page.waitForFunction(() => policyViolations.some(rule => rule.startsWith('script-src')));
      await page.evaluate(async () => {
        const response = await fetch('/api/original/soldier%2Fmedic');
        if (!response.ok) throw new Error('Original audio unavailable');
        const url = URL.createObjectURL(new Blob([await response.arrayBuffer()], {type:'audio/wav'}));
        const audio = document.createElement('audio');
        audio.id = 'policy-audio';
        audio.src = url;
        document.body.append(audio);
        await audio.play();
      });
      await page.waitForFunction(() => document.querySelector('#policy-audio').currentTime > 0);
      assert.equal(await page.evaluate(() => policyViolations.some(rule => rule.startsWith('media-src'))), false);
      await page.evaluate(() => {
        const audio = document.querySelector('#policy-audio');
        audio.pause();
        URL.revokeObjectURL(audio.src);
        audio.remove();
      });
    } else if (process.env.TF2RA_CASE === 'setup') {
      await expectVisible(page.locator('#setup-view'));
      await click(page, 'Start solo');
      await expectVisible(page.getByText('Choose your Team Fortress 2 folder before starting a recording.',{exact:true}));
      await page.locator('#tf-path').fill(path.join(process.env.TF2RA_TEMP, 'wrong'));
      await click(page, 'Use this folder');
      await expectVisible(page.locator('#setup-error'));
      await page.locator('#tf-path').fill(path.join(process.env.TF2RA_TEMP, 'Team Fortress 2'));
      await click(page, 'Use this folder');
      await expectVisible(page.getByRole('button',{name:/Soldier/}));
    }
    assert.deepEqual(errors, []);
  } finally { await browser.close(); }
})().catch(error => { console.error(error); process.exitCode = 1; });
"""
