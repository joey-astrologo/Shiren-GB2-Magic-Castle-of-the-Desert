# Rescue password converter website

Open [`index.html`](index.html) in a browser. The page works from a local folder as
well as GitHub Pages: there are no package installs, external scripts/fonts, fetches,
ROM files, account requirements, or backend services. Keep all five web files together:
`index.html`, `style.css`, `page.js`, `converter.js`, and `password-data.js`.

The [mission guide](../SPECIAL_RESCUE_MISSIONS.md) explains the three promotional
requests, original sources, supported passwords, and ROM audit.

## Host it on GitHub Pages

The repository includes
[`.github/workflows/rescue-converter-pages.yml`](../../.github/workflows/rescue-converter-pages.yml).
It tests the source-free converter and uploads only this website folder.

1. Commit/merge these files to the repository's **main** branch and **push them to
   GitHub**. The workflow must exist on GitHub's main branch before it can be run.
2. In the repository's **Settings → Pages → Build and deployment**, set **Source**
   to **GitHub Actions**.
   You may still see suggested **GitHub Pages Jekyll** and **Static HTML** cards with
   **Configure** buttons. Leave those alone: this repository already includes its
   own workflow, so this settings step is complete once the source is selected.
3. Leave Settings and open the repository's **Actions** tab at the top of the page.
   In its left sidebar, select **Rescue password converter**. This is a separate
   page from the **GitHub Actions** source dropdown in Pages settings.
   [Open this workflow directly](https://github.com/joey-astrologo/Shiren-GB2-Magic-Castle-of-the-Desert/actions/workflows/rescue-converter-pages.yml).
4. Above the list of runs, click **Run workflow** on the right. Leave **Branch: main**
   selected, then click the green **Run workflow** button inside the dropdown.
5. Refresh the runs list if needed and open the new run. Wait for both
   **check-and-upload** and **deploy** to turn green. The deploy job provides the site
   link; it also appears in **Settings → Pages** after deployment.

If **Rescue password converter** is missing, check that
[the workflow file exists on GitHub's main branch](https://github.com/joey-astrologo/Shiren-GB2-Magic-Castle-of-the-Desert/blob/main/.github/workflows/rescue-converter-pages.yml).
If GitHub prompts you to enable Actions for the repository, do that first. The manual
run button is on the individual workflow's page, not the general Actions overview.
GitHub documents these controls in [Manually running a workflow](https://docs.github.com/en/actions/how-tos/manage-workflow-runs/manually-run-a-workflow).

Later changes to the converter on main deploy automatically after its tests pass.

Once that deployment succeeds, the website is served at:

**https://joey-astrologo.github.io/Shiren-GB2-Magic-Castle-of-the-Desert/**

This is the expected deployment address, not a claim that the site has already been
published. The workflow intentionally does not deploy feature branches. For forks,
use the Pages URL shown by the workflow and update the footer's repository links.

See GitHub's [custom Pages workflow documentation](https://docs.github.com/en/pages/getting-started-with-github-pages/using-custom-workflows-with-github-pages).

## Maintain the mapping

`tools/rescue_password.py` owns the exact Japanese and English alphabets used by the
patch. `data/special_rescue_missions.json` owns the reviewed promotional codes and
source references. Regenerate their browser data after a deliberate source change:

```sh
python3 tools/rescue_converter.py --export-web-data docs/rescue-converter/password-data.js
```

`converter.js` transcribes packet decoding/checksum validation from the existing
Python codec. It maps symbols directly instead of regenerating packets, preserving
otherwise unused padding bits. `page.js` owns the form and mission presets.

With Python 3.9+ and Node.js installed, run:

```sh
python3 -m unittest tests.test_rescue_converter -v
```

The Node parity test uses `node` on PATH, or an executable path in **SHIREN_NODE**.
Without Node, that one test reports a skip; the Pages workflow requires Node so it
cannot silently skip JavaScript verification. The ROM/PyBoy route tests are separate:

```sh
python3 -m unittest tests.test_special_rescue_missions -v
```
