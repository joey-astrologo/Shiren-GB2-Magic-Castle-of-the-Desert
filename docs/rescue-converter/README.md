# Rescue password converter website

**[Open the hosted rescue password converter](https://joey-astrologo.github.io/Shiren-GB2-Magic-Castle-of-the-Desert/).**

The website is published on GitHub Pages. To use it offline, open [`index.html`](index.html)
in a browser. There are no package installs, external scripts/fonts, fetches, ROM files,
account requirements, or backend services. Keep all six web files together:
`index.html`, `style.css`, `page.js`, `i18n.js`, `converter.js`, and `password-data.js`.

The rescue converter is the hosted home page. Its bottom link opens the
[translation tool index](../translation-tool/README.md), which offers GB2 subject
workbenches with all extracted entries and included Japanese text. To preview that navigation locally, stage and
serve the combined site using the commands in the translation tool documentation.

Use **Language / 言語** at the top of the page to choose **English** or **日本語**.
The interface starts in Japanese for a Japanese browser locale and English otherwise;
an explicit choice is remembered when browser storage is available. Switching languages
preserves the input, conversion direction, and result. Labels, help, mission names,
validation messages, and clipboard feedback all follow the selected interface language.

The [mission guide](../SPECIAL_RESCUE_MISSIONS.md) explains the three promotional
requests, original sources, supported passwords, and ROM audit.

## GitHub Pages deployment

The repository includes
[`.github/workflows/rescue-converter-pages.yml`](../../.github/workflows/rescue-converter-pages.yml).
It tests the converter and GB2 prose/workbench rules, then runs `tools/build_pages.py` to stage an
explicit public-file allowlist in `build/pages`. The converter occupies the root and the
translation index/editor occupy `translation-tool/`. No ROM, save, raw extraction, test
page or build tool is uploaded. Changes on main deploy automatically after the checks
pass. The following setup steps
are for a fork or for configuring Pages again; the main project's setup is complete.

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

The workflow deploys main. For forks, use the Pages URL shown by the workflow and
update the footer's repository links.

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
otherwise unused padding bits. Its errors carry stable codes and details so that the page
can translate them without parsing English messages. `page.js` owns the form, language
selection, and mission presets; `i18n.js` owns both sets of interface text. Japanese dungeon
names come from the reviewed mission data. Keep translation keys and `{placeholder}` names
consistent between languages; update the English HTML fallback when changing visible copy.

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
