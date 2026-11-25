# License boundaries and sources

The root MIT license covers this project's original launcher, profiles, tests and
documentation. It does **not** relicense the following software or any games.

| Component | License / ownership | Source |
| --- | --- | --- |
| Steam browser-helper wrapper source | MIT, copyright 2026 notpop; original notice in `vendor/LICENSE.notpop` | https://github.com/notpop/steam-on-m1-wine |
| Wine stable 11.0_1 macOS distribution | Wine LGPL-2.1-or-later and component-specific notices in upstream distribution | https://github.com/Gcenx/macOS_Wine_builds/releases/tag/11.0_1 |
| DXVK macOS 1.10.3 repack | zlib license; retain upstream component notices | https://github.com/Gcenx/DXVK-macOS/releases/tag/v1.10.3-20230507-repack |
| Steam client and installer | Valve's proprietary terms | https://store.steampowered.com/about/ |
| Lethal Company | Proprietary; not included | https://store.steampowered.com/app/1966720/ |
| Counter-Strike 2 | Proprietary; not included | https://store.steampowered.com/app/730/ |

No third-party runtime binaries, game files, account data, or installer executables
are distributed in this repository. `install-runtime` downloads upstream archives
and verifies the exact digests recorded in `launcher.py` before extraction. The
Wine digest is published in its release metadata; the DXVK digest records the
upstream archive used during the original local setup. These are historical pins,
not a claim that those versions are currently newest or universally compatible.

The Steam installer is fetched from Valve's HTTPS endpoint. Valve replaces that
installer in place, so it is not pinned by checksum. Installing/using Steam or a
game remains subject to its own terms and any license you need to obtain it.
