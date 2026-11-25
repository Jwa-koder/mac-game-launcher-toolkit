# Mac Game Launcher Toolkit

MIT-licensed Python source for profile-driven Windows Steam launchers on Apple
Silicon. Includes **Lethal Company**, **Counter-Strike 2**, and a **blank profile**
ready to configure for another game.

This is a source toolkit, not a game download or a universal compatibility fix.
It does not include Wine, Steam, game files, accounts, saves, or compiled DLLs.

## What has been tested

The original local setup reached the menus of Lethal Company and CS2 on an M4 Mac
running macOS 15.7.3, using Wine 11.0, macOS DXVK 1.10.3, and the Steam helper
workaround below. The owner confirmed both menus were visible. These profiles
capture those launch settings; this newly generalized installer has automated
unit tests, not a new end-to-end test on every Mac or game version.

| Profile | Settings | Limits |
| --- | --- | --- |
| `lethal-company.json` | 30 FPS cap; requests 800×450 windowed | The game overrode resolution during testing. It is not a verified lowest-quality preset. |
| `counter-strike-2.json` | 960×540 fullscreen requested; 30 FPS cap | Menu reached; fullscreen was requested in the launch log. Online matchmaking/VAC and sustained gameplay are unverified. |
| `blank.json` | No app ID, executable, game arguments, or graphics patch | Deliberately refuses to launch until configured. |

Profiles use separate Wine prefixes by default. Do not point two running profiles
at the same prefix. The launcher supports the default Windows Steam library; custom
libraries and 32-bit games require changes. This is not the old macOS CS:GO build.

## Requirements

- Apple Silicon Mac, macOS 14 or newer, and **Python 3.12+**.
- Rosetta 2 installed through Apple's normal installation process.
- Enough disk space for the chosen game, its Steam client, runtime and updates.
- A Steam account and the relevant game license; authenticate in Valve's client.
- For the optional Steam workaround: `brew install mingw-w64` to compile its small
  wrapper locally. Homebrew and Rosetta are not installed automatically.

## Configure a blank launcher

```sh
python3 launcher.py init --output my-game.local.json
```

Edit that JSON. Set `name`, `steam_app_id` (a numeric **string**) and `executable`
(relative to the game's Steam install folder, using forward slashes). Add only
launch arguments supported by that game. `wine_binary` and `prefix` can be left
empty for the downloaded runtime and an isolated prefix, or set to local paths.
Files ending in `.local.json` are ignored by Git.

`dxvk_scope` is `none`, `game` (DLLs beside the executable), or `system` (DLLs in
this prefix's system32, with overrides scoped to the executable's basename).
The provided DXVK package is 64-bit DirectX 10/11 only, not DirectX 12. DLLs are
backed up before replacement. Do not blindly enable a graphics patch for every game.

`fps_cap` controls DXVK's frame limiter; other rendering backends may ignore it.
The CS2 profile also passes its own native FPS limits. `game_args` is an argument
array and is never evaluated through a shell.

Preview without installing or executing anything:

```sh
python3 launcher.py plan --profile my-game.local.json
python3 launcher.py doctor --profile profiles/lethal-company.json
```

`doctor` reports paths, flags and whether Wine exists. It does not certify game,
anti-cheat, display, or runtime compatibility.

## Install and launch

Use a profile consistently: each one has its own Steam installation and login.
Replace `profiles/lethal-company.json` below with your configured profile or the
CS2 profile when appropriate.

```sh
# Download checksum-verified pinned Wine/DXVK archives outside the repository.
python3 launcher.py install-runtime
# If the compiler was missing during installation, build the wrapper after installing it.
python3 launcher.py build-wrapper
python3 launcher.py setup --profile profiles/lethal-company.json
```

Let Steam complete its first self-update before applying the helper replacement.
For the included historical profiles, explicitly consent to the workaround:

```sh
python3 launcher.py bootstrap-steam --profile profiles/lethal-company.json --allow-steam-workaround
# After the first update, stop this prefix if it is still running.
python3 launcher.py stop --profile profiles/lethal-company.json
python3 launcher.py steam --profile profiles/lethal-company.json --allow-steam-workaround
# Sign in in Steam, then install the game there or use:
python3 launcher.py install-game --profile profiles/lethal-company.json --allow-steam-workaround
# Once Steam reports installation complete:
python3 launcher.py play --profile profiles/lethal-company.json --allow-steam-workaround
```

If Steam updated the helper while bootstrapping, another `stop` followed by `steam`
reapplies the reviewed wrapper. Close any game using this prefix before changing
its DLLs or helper. `stop` terminates all programs within that profile's prefix;
unsaved progress can be lost. There is intentionally no destructive reset command.

The blank template defaults to `steam_workaround: false`. If your runtime displays
Steam correctly without this workaround, leave it disabled and omit the consent
flag. If a pinned archive already exists, the installer asks you to move its
extracted directory aside before reinstalling; it does not overwrite runtimes.

## Steam workaround: review before enabling

For the two original profiles, the Steam Chromium interface was black until a
small MIT-licensed helper wrapper forced `--disable-gpu --single-process`.
Its source and upstream license are in `vendor/`. Steam's original helper is
preserved as `steamwebhelper_real.exe`.

Enabling this workaround **replaces that helper, disables Steam's Chromium sandbox,
and skips Steam's startup file verification** (`-noverifyfiles`). These reduce
Steam's protections. Commands that use it require `--allow-steam-workaround`;
merely previewing a plan does not make those changes. Steam's normal updates remain
enabled. The launcher does not remove quarantine, ad-hoc sign applications, change
Gatekeeper, install kernel drivers, or disable system security settings.

To undo the wrapper: stop the prefix, restore `steamwebhelper_real.exe` to
`steamwebhelper.exe`, set `steam_workaround` to false, and remove the workaround
flags from any external shortcuts. Steam can also repair its own files on a normal
verified launch. Restore `.before-mac-game-launcher` DLL backups and remove the
corresponding per-app Wine registry overrides to undo a graphics patch.

## Can this run any Windows game?

No. Treat each new profile as an experiment. Graphics APIs, Windows services,
DRM, CPU instructions and anti-cheat can prevent a game from working. Reaching a
menu does not prove multiplayer compatibility. **Valorant/Vanguard is unsupported**
by this Wine setup; a blank configuration cannot make a Windows kernel driver work.
Do not bypass anti-cheat or modify protected game binaries.

## Development and license

```sh
python3 -m unittest discover -s tests -v
```

Tests cover profile isolation, incomplete/escaping install paths, blank-template
validation, non-executing plans, checksum failures and wrapper backup handling.
They do not install or launch games. GitHub Actions runs them on Python 3.12.

Original project code, profiles and documentation: [MIT](LICENSE).
The included wrapper retains [notpop's MIT notice](vendor/LICENSE.notpop).
Games and downloaded third-party components retain their own licenses—see
[THIRD_PARTY.md](THIRD_PARTY.md). The MIT license does not grant game ownership.
