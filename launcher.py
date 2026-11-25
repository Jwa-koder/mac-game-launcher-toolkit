#!/usr/bin/env python3
"""MIT-licensed, profile-driven Windows Steam launcher for Apple Silicon."""
import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import platform
import re
import shutil
import subprocess
import sys
import tarfile
import urllib.request

ROOT = Path(__file__).resolve().parent
DATA = Path.home() / "Library/Application Support/MacGameLauncher"
ASSETS = DATA / "assets"
STEAM = r"C:\Program Files (x86)\Steam\steam.exe"
STEAM_URL = "https://cdn.cloudflare.steamstatic.com/client/installer/SteamSetup.exe"
PACKAGES = {
    "wine": (
        "https://github.com/Gcenx/macOS_Wine_builds/releases/download/11.0_1/wine-stable-11.0_1-osx64.tar.xz",
        "b50dc50ec7f41d58b115a6b685d4d1315ba3c797bd3aa0f49213f2703cb82388",
    ),
    "dxvk": (
        "https://github.com/Gcenx/DXVK-macOS/releases/download/v1.10.3-20230507-repack/dxvk-macOS-async-v1.10.3-20230507-repack.tar.gz",
        "acd1520ad105d8ef124a09c8e11a259a5dc8bdc565ad18e0e52693f9807b2477",
    ),
}


def digest(path):
    with Path(path).open("rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest()


def relative_path(value):
    if not isinstance(value, str) or not value or "\\" in value or ":" in value:
        raise ValueError("Game executable must be a relative path using forward slashes.")
    path = PurePosixPath(value)
    if path.is_absolute() or ".." in path.parts:
        raise ValueError("Game executable cannot escape the game's install folder.")
    return path


def load_profile(path):
    with Path(path).open(encoding="utf-8") as handle:
        profile = json.load(handle)
    if not isinstance(profile, dict):
        raise ValueError("The profile must be a JSON object.")
    if not isinstance(profile.get("name"), str) or not re.fullmatch(r"[a-z0-9][a-z0-9-]*", profile["name"]):
        raise ValueError("name must contain lowercase letters, numbers, and hyphens.")
    app = profile.get("steam_app_id")
    if not isinstance(app, str) or not re.fullmatch(r"[1-9][0-9]*", app):
        raise ValueError("Set steam_app_id to the game's numeric Steam app ID (as a string).")
    relative_path(profile.get("executable"))
    args = profile.get("game_args", [])
    if not isinstance(args, list) or not all(isinstance(item, str) for item in args):
        raise ValueError("game_args must be a list of strings.")
    fps = profile.get("fps_cap", 30)
    if type(fps) is not int or not 1 <= fps <= 1000:
        raise ValueError("fps_cap must be an integer from 1 to 1000.")
    if profile.get("dxvk_scope", "none") not in ("none", "game", "system"):
        raise ValueError("dxvk_scope must be none, game, or system.")
    if type(profile.get("steam_workaround", False)) is not bool:
        raise ValueError("steam_workaround must be true or false.")
    for key in ("wine_binary", "prefix"):
        if key in profile and not isinstance(profile[key], str):
            raise ValueError(f"{key} must be a path string.")
    return profile


def settings(profile):
    prefix = Path(profile.get("prefix") or DATA / "prefixes" / profile["name"]).expanduser().resolve()
    if prefix == Path.home() or prefix == Path("/"):
        raise ValueError("Choose a dedicated Wine prefix, not your home or root directory.")
    wine = Path(profile.get("wine_binary") or ASSETS / "wine/Wine Stable.app/Contents/Resources/wine/bin/wine").expanduser().resolve()
    env = os.environ.copy()
    env.update(WINEPREFIX=str(prefix), WINEESYNC="1", WINEDEBUG="-all",
               ROSETTA_ADVERTISE_AVX="1", MVK_CONFIG_LOG_LEVEL="0",
               DXVK_FRAME_RATE=str(profile.get("fps_cap", 30)),
               WINEDLLOVERRIDES="bcrypt=b;ncrypt=b;gameoverlayrenderer,gameoverlayrenderer64=d")
    flags = ["-noverifyfiles", "-no-cef-sandbox", "-cef-single-process"] if profile.get("steam_workaround") else []
    return prefix, wine, env, flags


def run_wine(wine, env, *args):
    command = ["arch", "-x86_64", str(wine), *args]
    result = subprocess.run(command, env=env, check=False)
    # Steam's updater deliberately hands off to a replacement client with code 42.
    if not (args and args[0] == STEAM and result.returncode == 42):
        result.check_returncode()


def download(url, target, sha256=None):
    target = Path(target)
    target.parent.mkdir(parents=True, exist_ok=True)
    partial = target.with_name(target.name + ".partial")
    try:
        urllib.request.urlretrieve(url, partial)
        if sha256 and digest(partial) != sha256:
            raise ValueError(f"Checksum mismatch for {target.name}; nothing was installed.")
        partial.replace(target)
    finally:
        partial.unlink(missing_ok=True)


def install_runtime():
    for name, (url, sha256) in PACKAGES.items():
        destination = ASSETS / name
        if destination.exists():
            raise ValueError(f"{destination} already exists. Move it aside before reinstalling.")
        archive = ASSETS / "downloads" / url.rsplit("/", 1)[1]
        download(url, archive, sha256)
        destination.mkdir(parents=True)
        try:
            with tarfile.open(archive) as contents:
                contents.extractall(destination, filter="data")
        except Exception:
            shutil.rmtree(destination)
            raise
        print(f"Installed checksum-verified {name}: {destination}")
    compiler = shutil.which("x86_64-w64-mingw32-gcc")
    if not compiler:
        print("For the optional Steam rendering workaround, install mingw-w64 and run build-wrapper.")
    else:
        build_wrapper()


def build_wrapper():
    compiler = shutil.which("x86_64-w64-mingw32-gcc")
    if not compiler:
        raise ValueError("Install the cross-compiler first: brew install mingw-w64")
    target = ASSETS / "steamwebhelper.exe"
    target.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run([compiler, "-O2", "-Wall", "-Wextra", "-municode", "-DUNICODE", "-D_UNICODE",
                    str(ROOT / "vendor/steamwebhelper-wrapper.c"), "-o", str(target),
                    "-static", "-lshell32", "-mwindows"], check=True)
    print(f"Compiled rendering wrapper locally: {target}")


def apply_steam_fix(prefix):
    helper = prefix / "drive_c/Program Files (x86)/Steam/bin/cef/cef.win64/steamwebhelper.exe"
    wrapper = ASSETS / "steamwebhelper.exe"
    original = helper.with_name("steamwebhelper_real.exe")
    if not wrapper.is_file() or not helper.is_file():
        raise ValueError("Steam or the wrapper is missing. Complete setup/build-wrapper and Steam's first update, then retry.")
    if digest(helper) == digest(wrapper):
        if not original.is_file() or original.stat().st_size < 500000:
            raise ValueError("Original Valve helper is missing; repair Steam before continuing.")
        return
    if helper.stat().st_size < 500000:
        raise ValueError("Unrecognized helper; refusing to overwrite it.")
    shutil.copy2(helper, original)
    temporary = helper.with_name("steamwebhelper.new")
    shutil.copy2(wrapper, temporary)
    temporary.replace(helper)


def game_folder(prefix, app):
    steam = prefix / "drive_c/Program Files (x86)/Steam"
    manifest = steam / "steamapps" / f"appmanifest_{app}.acf"
    if not manifest.is_file():
        raise ValueError("Install the Windows game in this prefix's default Steam library first.")
    text = manifest.read_text(encoding="utf-8")
    state = re.search(r'"StateFlags"\s+"(\d+)"', text)
    folder = re.search(r'"installdir"\s+"([^"/\\]+)"', text)
    if not state or not (int(state[1]) & 4) or not folder or folder[1] in (".", ".."):
        raise ValueError("The Steam installation is incomplete or its manifest is invalid.")
    common = (steam / "steamapps/common").resolve()
    game = (common / folder[1]).resolve()
    if not game.is_relative_to(common):
        raise ValueError("Game install path escapes the Steam library.")
    return game


def apply_graphics(profile, prefix, wine, env, game):
    executable = game.joinpath(*relative_path(profile["executable"]).parts).resolve()
    if not executable.is_relative_to(game) or not executable.is_file():
        raise ValueError("Configured game executable is missing or outside the install folder.")
    scope = profile.get("dxvk_scope", "none")
    if scope == "none":
        return
    dlls = list((ASSETS / "dxvk").glob("*/x64/*.dll"))
    if not dlls:
        raise ValueError("DXVK is missing. Run install-runtime first.")
    destination = executable.parent if scope == "game" else prefix / "drive_c/windows/system32"
    for source in dlls:
        target = destination / source.name
        if target.exists() and digest(source) == digest(target):
            continue
        backup = target.with_name(target.name + ".before-mac-game-launcher")
        if target.exists() and not backup.exists():
            shutil.copy2(target, backup)
        shutil.copy2(source, target)
    key = rf"HKCU\Software\Wine\AppDefaults\{executable.name}\DllOverrides"
    for name in ("d3d11", "d3d10core"):
        run_wine(wine, env, "reg", "add", key, "/v", name, "/t", "REG_SZ", "/d", "native,builtin", "/f")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["init", "plan", "doctor", "install-runtime", "build-wrapper", "setup", "bootstrap-steam", "steam", "install-game", "play", "stop"])
    parser.add_argument("--profile", type=Path, default=ROOT / "profiles/blank.json")
    parser.add_argument("--output", type=Path, help="Destination for init; never overwrites a file.")
    parser.add_argument("--allow-steam-workaround", action="store_true",
                        help="Explicitly allow Steam sandbox/file-check changes and helper replacement.")
    args = parser.parse_args(argv)
    if args.command == "init":
        if not args.output:
            parser.error("init requires --output your-game.json")
        with args.output.open("x", encoding="utf-8") as handle:
            handle.write((ROOT / "profiles/blank.json").read_text())
        print(f"Created blank profile: {args.output}. Fill in its app ID and executable.")
        return
    if args.command in ("install-runtime", "build-wrapper"):
        if sys.platform != "darwin" or platform.machine() != "arm64":
            raise ValueError("Runtime installation/build is for Apple Silicon macOS.")
        return install_runtime() if args.command == "install-runtime" else build_wrapper()
    profile = load_profile(args.profile)
    prefix, wine, env, flags = settings(profile)
    if args.command in ("plan", "doctor"):
        print(json.dumps({"profile": profile["name"], "prefix": str(prefix), "wine": str(wine),
                          "wine_exists": wine.is_file(), "steam_flags": flags,
                          "game_command": [STEAM, *flags, "-applaunch", profile["steam_app_id"], *profile.get("game_args", [])],
                          "fps_cap": env["DXVK_FRAME_RATE"], "steam_workaround_requires_consent": bool(flags)}, indent=2))
        return
    if sys.platform != "darwin" or platform.machine() != "arm64":
        raise ValueError("Launching requires Apple Silicon macOS and Rosetta 2.")
    if not wine.is_file():
        raise ValueError("Wine is missing. Run install-runtime or set wine_binary in the profile.")
    if profile.get("steam_workaround") and args.command in ("bootstrap-steam", "steam", "install-game", "play") and not args.allow_steam_workaround:
        raise ValueError("This profile replaces Steam's browser helper, disables its Chromium sandbox, and skips startup file checks. Review README, then explicitly add --allow-steam-workaround.")
    if args.command == "stop":
        subprocess.run(["arch", "-x86_64", str(wine.with_name("wineserver")), "-k"], env=env, check=True)
        return
    if args.command == "setup":
        prefix.mkdir(parents=True, exist_ok=True)
        run_wine(wine, env, "wineboot", "--init")
        run_wine(wine, env, "winecfg", "-v", "win10")
        installer = ASSETS / "downloads/SteamSetup.exe"
        # Valve replaces this official installer in place; it has no pinned digest.
        download(STEAM_URL, installer)
        run_wine(wine, env, str(installer), "/S")
        print("Steam installed. Launch Steam and complete its first update; build/apply the optional wrapper afterwards.")
        return
    if args.command == "bootstrap-steam":
        run_wine(wine, env, STEAM, *flags)
        return
    if profile.get("steam_workaround"):
        apply_steam_fix(prefix)
    if args.command == "steam":
        run_wine(wine, env, STEAM, *flags)
    elif args.command == "install-game":
        run_wine(wine, env, STEAM, *flags, "-console", "+app_install", profile["steam_app_id"], "0")
    elif args.command == "play":
        game = game_folder(prefix, profile["steam_app_id"])
        apply_graphics(profile, prefix, wine, env, game)
        run_wine(wine, env, STEAM, *flags, "-applaunch", profile["steam_app_id"], *profile.get("game_args", []))


if __name__ == "__main__":
    try:
        main()
    except (ValueError, OSError, subprocess.CalledProcessError) as error:
        print(f"Error: {error}", file=sys.stderr)
        sys.exit(1)
