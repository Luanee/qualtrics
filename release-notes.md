# Release Notes

## 0.2.0 (2026-09-03)

### Features

* ✨ feat: add multi-survey entity workflows. PR [#14](https://github.com/Luanee/qualtrics/pull/14) by [@Luanee](https://github.com/Luanee).

### Fixes

* 🐛 fix: dispatch standalone publication workflow. PR [#13](https://github.com/Luanee/qualtrics/pull/13) by [@Luanee](https://github.com/Luanee).

### Other changes

* 🔖 Fix PyPI trusted publishing workflow identity. PR [#12](https://github.com/Luanee/qualtrics/pull/12) by [@Luanee](https://github.com/Luanee).
* 🔖 Improve multi-survey report analytics and filtering. PR [#15](https://github.com/Luanee/qualtrics/pull/15) by [@Luanee](https://github.com/Luanee).
* 🔖 Add multi-survey entity workflows. PR [#16](https://github.com/Luanee/qualtrics/pull/16) by [@Luanee](https://github.com/Luanee).
* 🔖 Establish stable Qualtrics entity and question identity. PR [#17](https://github.com/Luanee/qualtrics/pull/17) by [@Luanee](https://github.com/Luanee).
* 🔖 Add analysis-ready Qualtrics response-answer facts. PR [#18](https://github.com/Luanee/qualtrics/pull/18) by [@Luanee](https://github.com/Luanee).
* 🔖 Enforce and serialize the normalized Qualtrics entity contract. PR [#19](https://github.com/Luanee/qualtrics/pull/19) by [@Luanee](https://github.com/Luanee).
* 🔖 Add Power BI-ready Qualtrics semantic model exports. PR [#20](https://github.com/Luanee/qualtrics/pull/20) by [@Luanee](https://github.com/Luanee).

## 0.1.2 (2026-08-31)

### Internal

* 👷 ci: automate pull request based releases. PR [#7](https://github.com/Luanee/qualtrics/pull/7) by [@Luanee](https://github.com/Luanee).

### Other changes

* 🔖 Load dotenv configuration and preserve survey definition metadata. PR [#8](https://github.com/Luanee/qualtrics/pull/8) by [@Luanee](https://github.com/Luanee).
* 🔖 Parse Qualtrics exports and improve question analytics. PR [#9](https://github.com/Luanee/qualtrics/pull/9) by [@Luanee](https://github.com/Luanee).
* 🔖 Add end-to-end survey export workflow and simplify documentation. PR [#10](https://github.com/Luanee/qualtrics/pull/10) by [@Luanee](https://github.com/Luanee).

## 0.1.1 (2026-08-30)

### Features

* ✨ initialize qualtrics toolkit. [38c6af7](https://github.com/Luanee/qualtrics/commit/38c6af711a13ae53a2cc8544bb3e9e1bdeafd64b)

### Refactors

* ♻️ split toolkit into domain modules. [fb6f7d5](https://github.com/Luanee/qualtrics/commit/fb6f7d5718d6028367ca95db47026b2fb5e657a6)
* ♻️ simplify response export formats. [a09f509](https://github.com/Luanee/qualtrics/commit/a09f5095a126797aa16137f7f72309cbcbbafea0)
* ♻️ rename package to qualtrics. [d579fc9](https://github.com/Luanee/qualtrics/commit/d579fc9d4e69dfa9cb969521f1deea60d0ca99ed)

### Documentation

* 📝 add typer usage examples. [21c691d](https://github.com/Luanee/qualtrics/commit/21c691da0a9f87961ab1cf7b08d5c37f0aa2621c)
* 📝 update package branding. [1283363](https://github.com/Luanee/qualtrics/commit/1283363958f0ed3e056e9289aaa962c35b8f0392)

### Internal

* ✅ cover parsing reporting and api domains. [ccf1a27](https://github.com/Luanee/qualtrics/commit/ccf1a2741edff210fd1c5e4d910252f36d287317)
* 🔧 configure vscode workspace. [6975231](https://github.com/Luanee/qualtrics/commit/6975231eb6144ef464e79a8a843d886744a569d2)
* 👷 modernize project tooling. [938fc31](https://github.com/Luanee/qualtrics/commit/938fc31e8406dcac53cf49dd1b26f1faa0d9d8dd)
* 👷 add pre-commit quality gates. [14a5594](https://github.com/Luanee/qualtrics/commit/14a5594b817490cc7745535c19529ca17110b613)
* 👷 add github automation. [b9a56be](https://github.com/Luanee/qualtrics/commit/b9a56be075ef9682cacd3b2f82c7f5bb83969969)
* 👷 harden build and release workflows. [23202a5](https://github.com/Luanee/qualtrics/commit/23202a55e0c7b1449cff4de5e1729b89243e54dc)
* 👷 automate release preparation. [7acac84](https://github.com/Luanee/qualtrics/commit/7acac84975be9d5b82c8fbc79da63ea8576bd898)
* 👷 bump actions/attest-build-provenance from 3 to 4. [d8aba82](https://github.com/Luanee/qualtrics/commit/d8aba82e29278c6910236f3d699dabd7a276c35c)
* 👷 bump pypa/gh-action-pypi-publish from 1.13.0 to 1.14.2. [2b7d969](https://github.com/Luanee/qualtrics/commit/2b7d96945e4a0fe152ee1220b465c4ed016b91af)
* 👷 bump actions/download-artifact from 5 to 8. [64fb5aa](https://github.com/Luanee/qualtrics/commit/64fb5aa0421733825636563fd1d9d81a8bbae5ec)
* 👷 bump actions/upload-artifact from 4 to 7. [09c1e95](https://github.com/Luanee/qualtrics/commit/09c1e9521c0dc5fd59435e55a425c031cad0f627)
* 🔧 define repository code owner. [d64f825](https://github.com/Luanee/qualtrics/commit/d64f825dd239b2ef2d171d462a8411c7bd1e0ece)

### Other changes

* 🔖 Merge pull request #1 from Luanee/dependabot/github_actions/actions/attest-build-provenance-4. [45d8c5f](https://github.com/Luanee/qualtrics/commit/45d8c5f6b4b3ae89243383085ff81bf9c9703d59)
* 🔖 Merge pull request #2 from Luanee/dependabot/github_actions/pypa/gh-action-pypi-publish-1.14.2. [e0871c2](https://github.com/Luanee/qualtrics/commit/e0871c23181f4c8ee3af1f867996de644d265213)
* 🔖 Merge pull request #3 from Luanee/dependabot/github_actions/actions/download-artifact-8. [d3bb937](https://github.com/Luanee/qualtrics/commit/d3bb9371fce74030b13fd83990b7758982ef0a35)
* 🔖 Merge pull request #4 from Luanee/dependabot/github_actions/actions/upload-artifact-7. [bbce4b2](https://github.com/Luanee/qualtrics/commit/bbce4b23bac5ed2d5df82b752822a0fb4468e1c5)
* 🔖 Merge pull request #5 from Luanee/update-readme-branding. [6ca8a0c](https://github.com/Luanee/qualtrics/commit/6ca8a0c8d23b3e294516c8ca96a91565448c5b87)

## 0.1.0 (2026-08-30)

### Features

- ✨ Introduce the typed Qualtrics API client, survey-response parser, entity exports, analytics, and HTML reporting.

### Documentation

- 📝 Add Typer-based examples for API access and offline survey parsing.

### Internal

- 👷 Add Ruff, `ty`, pytest coverage, pre-commit, GitHub CI, trusted publishing, and Dependabot automation.
