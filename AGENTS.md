# Mac Game Launcher Toolkit

Inherits ../AGENTS.md. Use feature branches and PR review/checks before merging.

Python 3.12+, standard library only. Run `python3 -m unittest discover -s tests -v`.
Never commit Wine prefixes, Steam accounts, saves, games, downloaded archives,
binaries, local absolute paths, credentials, or user-generated logs.
Our launcher/profiles/docs are MIT; retain vendor/LICENSE.notpop for the upstream wrapper.
Third-party runtimes and games retain their own licenses and are downloaded separately.

Current status: configurable launcher plus Lethal Company/CS2 profiles and a blank template.
Historical menu verification applies to one M4 Mac, not a universal compatibility guarantee.
CS2 online matchmaking remains unverified; Valorant/Vanguard is unsupported.
