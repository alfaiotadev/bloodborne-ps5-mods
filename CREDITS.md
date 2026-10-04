# Credits and acknowledgements

This project stands on the shoulders of the PS5 homebrew and reverse-engineering community. Everything below was used, studied or built upon while making these mods. If you notice a missing or wrong attribution, please open an issue or pull request and it will be fixed right away.

## Lance McDonald — the Bloodborne 60 FPS patch

The **60 FPS** mod in this repository is based on the work of **Lance McDonald**, who reverse-engineered and published the *Bloodborne 1.09 60 FPS patch* (the `720p.exe` / `1080p.exe` patchers for a decrypted `eboot.bin`, distributed on NexusMods as "BB 60FPS Patch"). The list of memory locations and byte values used by the `60 FPS (Lance McDonald)` cheat entry was derived from that patch, translated into an onionHEN cheat entry that is applied to the running game instead of rewriting `eboot.bin`. All credit for finding which instructions control the frame-rate cap, the simulation time step and the related resolution constants belongs to him. His readme says it best: *"This was made with love by Lance McDonald."*

This repository does **not** contain his executables, and the 60 FPS cheat entry is provided for interoperability with onionHEN; please support the original author. Lance's work was also our reference point for the resolution experiments (the `720p` and `1080p` variants), which are documented in `docs/`.

## Community game-patch lists

The byte patches behind **No Motion Blur**, **No Chromatic Aberration**, **Skip Intro Logos**, **DLC Save Requirement Unlock** and the write list of the 60 FPS cheat come from the community patch lists for `CUSA03173`: **[illusionyy/PS4-PS5-Game-Patch](https://github.com/illusionyy/PS4-PS5-Game-Patch)** and **[illusionyy/libhijacker-game-patch](https://github.com/illusionyy/libhijacker-game-patch)**, whose Bloodborne 60 FPS entry in turn follows Lance McDonald's work. They were transcribed into onionHEN's cheat-JSON format and checked entry by entry against the original instruction bytes of the game (`tools/mods/verify_against_dump.py`). Thank you to the maintainers and contributors of those lists.

## OnionHEN and the PS5 payload ecosystem

- **[onionHEN](https://github.com/aydencharles/onionHEN)** by *aydencharles* and contributors (GPL-3.0). The cheat engine, ShellUI Toolbox and in-game overlay that these mods run on. `onionhen/onionhen-bloodborne.patch` contains our changes on top of upstream commit `b23ffe6`.
- **[etaHEN](https://github.com/LightningMods/etaHEN)** by *LightningMods* and contributors — the source base of the onionHEN tree.
- **[GoldHEN](https://github.com/GoldHEN/GoldHEN)** by *SiSTR0* and contributors — the PS4 all-in-one HEN that onionHEN takes after.
- **[kstuff-lite](https://github.com/EchoStretch/kstuff-lite)** by *EchoStretch*, *sleirsgoevy* and contributors — kernel patches (fSELF/PKG support) used in the working payload chain.
- **[PS5 Payload SDK](https://github.com/ps5-payload-dev/sdk)** and **[elfldr](https://github.com/ps5-payload-dev/elfldr)** by the *ps5-payload-dev* team — the toolchain used to build onionHEN and the first-hop ELF loader on port 9021.
- **[libhijacker](https://github.com/astrelsky/libhijacker)** by *astrelsky* and **[NineS](https://github.com/buzzer-re/NineS)** by *buzzer-re* — process hijacking and ShellUI injection used inside onionHEN.
- **[HEN-Cheats-Collection](https://github.com/TeeKay87/HEN-Cheats-Collection)** by *TeeKay87* and **PHU Games Tools** by *ArkSama* — referenced by onionHEN for the community cheat format and the in-game FPS counter.
- **cJSON** (Dave Gamble), **miniz** (Rich Geldreich) and the **7-Zip LZMA SDK** (Igor Pavlov) — libraries embedded in onionHEN.
- **[PS5 WebKit Autoloader](https://github.com/itsPLK/ps5-webkit-autoloader)** and **PKG-Manager** by *itsPLK* — the autoloader app and package installer used on the development console. The exploit chain the autoloader runs is credited in its own repository, together with the authors of the individual exploits.
- **[ps5debug-NG](https://itsplk.github.io/ps5-payloads-mirror/payloads.json)** — the PS5 debugger payload (port 744) that all of our live-memory research tools talk to. Its authors are credited in the payload repository it is distributed from.
- **[ftpsrv](https://github.com/drakmor/ftpsrv)**, **ShadowMount+** and **[nanoDNS](https://github.com/drakmor/nanoDNS)** by *drakmor* and contributors — used in the development setup.

## Research and tooling

- **[Capstone](https://www.capstone-engine.org/)** (Nguyen Anh Quynh and contributors) for disassembly of the game's code during analysis.
- **NumPy**, **Pillow** and **[imagecodecs](https://github.com/cgohlke/imagecodecs)** (Christoph Gohlke) for decoding the PS5's JPEG XR screenshots and measuring image sharpness.
- **ImageMagick**, **curl**, **Docker**, **LLVM/Clang**, **CMake**, **Python** and **Git** for the everyday plumbing.
- The *Havok* physics/animation types (`hkQsTransform`, `hkaPose`, `hkbCharacter`) and the *YEBIS* post-effect library names that appear in the game's own debug strings made much of the camera and anti-aliasing research possible; they are referred to here purely for interoperability research.

## AI assistance

The analysis, tools and documentation in this repository were developed together with **Claude** (Anthropic) through Claude Code. All findings were verified on real hardware, and the repository documents negative results as well as positive ones so that the next person does not repeat them.

## Trademarks and legal

*Bloodborne* is a trademark of Sony Interactive Entertainment and FromSoftware. This project is **not affiliated with or endorsed by** Sony Interactive Entertainment, FromSoftware, onionHEN, Lance McDonald or any other party named above. It contains no game assets, no game binaries and no memory dumps; you must own a legitimate copy of the game and use the mods only on hardware you own. Use at your own risk.
