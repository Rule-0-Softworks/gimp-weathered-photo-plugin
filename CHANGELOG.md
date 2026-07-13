# Changelog

## [0.2.0](https://github.com/Rule-0-Softworks/gimp-weathered-photo-plugin/compare/gimp-weathered-photo-plugin-v0.1.0...gimp-weathered-photo-plugin-v0.2.0) (2026-07-13)


### Features

* add batch CLI and curated GIMP assets ([9c82953](https://github.com/Rule-0-Softworks/gimp-weathered-photo-plugin/commit/9c82953f708cb4dd3cb62a878d25e9b77def49b0))
* add native recipe operation contract ([aad6a5c](https://github.com/Rule-0-Softworks/gimp-weathered-photo-plugin/commit/aad6a5c8d61eba42c3d3bb924dfa6ba58e19b553))
* add replay-safe weathered photo batch pipeline ([9dbdb43](https://github.com/Rule-0-Softworks/gimp-weathered-photo-plugin/commit/9dbdb432b41d49f2a6c5f907a97573a2df385461))
* **analyzer:** use mediapipe tasks landmarks ([0a06ed0](https://github.com/Rule-0-Softworks/gimp-weathered-photo-plugin/commit/0a06ed039f32cf14e6aa8b4ea317bafc8a382657))
* bridge staged semantic analysis ([726ba52](https://github.com/Rule-0-Softworks/gimp-weathered-photo-plugin/commit/726ba527a2bcc5f8eefda59ecd5073cd543d4edf))
* **bridge:** record verified model provenance ([3b5cb59](https://github.com/Rule-0-Softworks/gimp-weathered-photo-plugin/commit/3b5cb59f744b8e4bc9ebe8108e3de21c8e9bd697))
* guard staged output publication ([844b6f0](https://github.com/Rule-0-Softworks/gimp-weathered-photo-plugin/commit/844b6f0f850f46af015c97e44eb48f0210a7136f))
* **metadata:** persist model analysis provenance ([cdb6207](https://github.com/Rule-0-Softworks/gimp-weathered-photo-plugin/commit/cdb6207021caab145dc47929524573080749f22e))
* **models:** add verified mediapipe task assets ([00d7ac9](https://github.com/Rule-0-Softworks/gimp-weathered-photo-plugin/commit/00d7ac9eb0f8f285892b681c951e4cd11e84130c))
* publish replay-safe render sets ([a785a23](https://github.com/Rule-0-Softworks/gimp-weathered-photo-plugin/commit/a785a2329195b58c0c023eba33253db587d66c2e))
* render bridge recipes in gimp ([fc0d6f2](https://github.com/Rule-0-Softworks/gimp-weathered-photo-plugin/commit/fc0d6f2b9588ca4353b7a06957bdae97fabd31b3))
* stage replay-safe batch outputs ([6271b1f](https://github.com/Rule-0-Softworks/gimp-weathered-photo-plugin/commit/6271b1f9fbf396c82eba34aaede8cda5c3ebbc6c))


### Bug Fixes

* address renderer review feedback ([894b621](https://github.com/Rule-0-Softworks/gimp-weathered-photo-plugin/commit/894b6211dc56e19a16774f29a5f4347e1d0110d2))
* **analyzer:** validate tasks images before opencv import ([cccb4e0](https://github.com/Rule-0-Softworks/gimp-weathered-photo-plugin/commit/cccb4e02e2d8683feb9ae9b5b2f99dfd143f1422))
* **batch:** validate replay publication invariants ([9ea5de2](https://github.com/Rule-0-Softworks/gimp-weathered-photo-plugin/commit/9ea5de24c7682a8d78c5e551d25c0484260f333b))
* **bridge:** add analyzer module entrypoint ([b580c29](https://github.com/Rule-0-Softworks/gimp-weathered-photo-plugin/commit/b580c296846bd9bff61772ac7533eff6fefaab0b))
* **bridge:** classify dependency failures ([574c3eb](https://github.com/Rule-0-Softworks/gimp-weathered-photo-plugin/commit/574c3ebf8e0fb01013940388492d29691eece483))
* **ci:** install mediapipe egl runtime ([84c8c00](https://github.com/Rule-0-Softworks/gimp-weathered-photo-plugin/commit/84c8c00bcf75bc56da56773fe6c5d2e245152979))
* **ci:** support mediapipe checks on ubuntu ([cc6477e](https://github.com/Rule-0-Softworks/gimp-weathered-photo-plugin/commit/cc6477ebd9997a4a96243fd2f9de02ef96e3e477))
* **gimp:** constrain native water stain rendering ([ac8882f](https://github.com/Rule-0-Softworks/gimp-weathered-photo-plugin/commit/ac8882ffd873244ef7a826bc750004aedea3ece6))
* **gimp:** convert brush rotations to radians ([32aa871](https://github.com/Rule-0-Softworks/gimp-weathered-photo-plugin/commit/32aa871e05c1738e1e239404157b0f25e3506d63))
* **gimp:** mask water stains and source alpha ([6fafcd4](https://github.com/Rule-0-Softworks/gimp-weathered-photo-plugin/commit/6fafcd43d3c4f6907b1d43c4918e0116f14212fb))
* lower coverage thresholds to 75% ([e92a0f9](https://github.com/Rule-0-Softworks/gimp-weathered-photo-plugin/commit/e92a0f9effa0d0c1f13b7415f45bfd791404880b))
* **models:** reject unknown advisory model ids ([0eee897](https://github.com/Rule-0-Softworks/gimp-weathered-photo-plugin/commit/0eee897dfd603517170708ec18f60a8917cbd1b7))
* **provenance:** harden immutable model metadata ([0309ac5](https://github.com/Rule-0-Softworks/gimp-weathered-photo-plugin/commit/0309ac5dd49b9f735357faa3cce50245b4a07ba0))


### Documentation

* add mediapipe tasks model asset design ([008deff](https://github.com/Rule-0-Softworks/gimp-weathered-photo-plugin/commit/008deffe4b22d88bdaed1e6da8f2a11c04cfb5f3))

## 0.1.0 (2026-07-13)


### Features

* Add initial project scaffolding for the GIMP weathered photo plugin ([5a5d2c5](https://github.com/Rule-0-Softworks/gimp-weathered-photo-plugin/commit/5a5d2c59d2d712fc7c8abd89601b8095253312cf))


### Bug Fixes

* **ci:** harden Dependabot pull request checks ([38404f7](https://github.com/Rule-0-Softworks/gimp-weathered-photo-plugin/commit/38404f71becc427495cc389e8a636ca765943777))


### Documentation

* add contributor setup and project layout ([55c09ac](https://github.com/Rule-0-Softworks/gimp-weathered-photo-plugin/commit/55c09ac9cd4b6dde5e13240896faca3167f5673b))
* add initial scaffold implementation plan ([eeeee11](https://github.com/Rule-0-Softworks/gimp-weathered-photo-plugin/commit/eeeee112cfce4a2033b0f6524420a870bd67b46a))
* clarify scaffold validation ([e958212](https://github.com/Rule-0-Softworks/gimp-weathered-photo-plugin/commit/e95821212fc0d9a09abe700866e3d2231cfd4a32))
* correct scaffold scope verification ([6ac50e0](https://github.com/Rule-0-Softworks/gimp-weathered-photo-plugin/commit/6ac50e026f725c58a3bf8c6a2d3d7d61b0ab5686))
* correct scaffold sync sequence ([c58d114](https://github.com/Rule-0-Softworks/gimp-weathered-photo-plugin/commit/c58d11497cd9ec8915ae09567b24afa1d0163e1a))
* define initial scaffold design ([109c94a](https://github.com/Rule-0-Softworks/gimp-weathered-photo-plugin/commit/109c94ae93c9d2a85bbac5755b55c28983afff51))
* define public readme presentation ([5f67f85](https://github.com/Rule-0-Softworks/gimp-weathered-photo-plugin/commit/5f67f8592047eea7f48f284f73ee85c6ae9c3168))
* polish public readme ([d342e3c](https://github.com/Rule-0-Softworks/gimp-weathered-photo-plugin/commit/d342e3ceec152266cf26a2e73f32b3f5238f9cef))
* target python 3.12 ([7f72a55](https://github.com/Rule-0-Softworks/gimp-weathered-photo-plugin/commit/7f72a55bdbc08d95f955e074ddb9bb26c0cfaf8d))
