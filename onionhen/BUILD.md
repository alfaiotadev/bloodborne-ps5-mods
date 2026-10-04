# Building the patched onionHEN

`onionhen-bloodborne.patch` is a patch against upstream **onionHEN** ([aydencharles/onionHEN](https://github.com/aydencharles/onionHEN), GPL-3.0), base commit `b23ffe6`. It contains the changes the mods and the research tooling rely on:

- **Exec-time auto-apply:** cheats marked enabled are written when the game process starts (the process is stopped briefly, the patches are written atomically).
- **XOM fallback** for code pages that are execute-only, and a **non-destructive code-cave** allocator.
- Per-cheat **`enabled` flag** handling in the JSON parser/applier.
- **Screenshot hook:** a request file makes the ShellUI replay the system screenshot, which the research automation uses (`tools/dev/`).
- A game **monitor overlay** extension (FPS/probe values).

> Tested only with firmware 12.40 on a PS5 Pro. The patched build is **required** for `cheats/CUSA03173_01.09.json`: stock onionHEN has no launch-time apply, no code-cave allocator and no `enabled` flag, and was not tested with these cheat files.

## Apply the patch

```sh
git clone https://github.com/aydencharles/onionHEN
cd onionHEN
git checkout b23ffe6
git apply ../bloodborne-ps5-mods/onionhen/onionhen-bloodborne.patch
```

## Build (Docker)

The upstream `Dockerfile` builds the toolchain image once (about 20 minutes):

```sh
docker build -t onionhen-build .
```

The PS5 payload SDK needs the pacbrew packages (curl, ca-bundle) mounted into the SDK; unpack the `ps5-payload-dev` pacbrew tarball of the SDK release you use (`opt/ps5-payload-sdk/target/user/homebrew`) into `.docker/pacbrew-ps5`. Then (about 4 minutes):

```sh
docker run --rm -v $PWD:/workspace \
  -v $PWD/.docker/pacbrew-ps5:/opt/ps5-payload-sdk/target/user/homebrew:ro \
  -w /workspace onionhen-build /bin/bash -c \
  'rm -rf /tmp/bb-build; mkdir -p /tmp/bb-build; cp -a /workspace/. /tmp/bb-build/;
   cd /tmp/bb-build; export PS5_PAYLOAD_SDK=/opt/ps5-payload-sdk \
   LLVM_CONFIG=/usr/lib/llvm-18/bin/llvm-config \
   PATH=/usr/lib/llvm-18/bin:/opt/ps5-payload-sdk/bin:$PATH;
   ./scripts/build.sh --release --jobs 8;
   rm -rf /workspace/build; cp -a /tmp/bb-build/build /workspace/build'
```

Outputs are in `build/bin/`: `OnionHEN.elf`, `bootstrapper.elf`, `shellui.elf`, ...

## Deploy

`OnionHEN.elf` goes where your autoloader expects the onionHEN payload (for the WebKit autoloader setup used during development: `/data/ps5_autoloader/onionHEN.elf`), `bootstrapper.elf` to `/data/OnionHEN/onionhen.elf`; then restart the payload chain. Check your setup's own documentation - the paths depend on the loader.

## Prebuilt files

The ELFs built from this patch are attached to the **Releases** page together with their checksums (`SHA1SUMS` in this folder lists the v0.0.15-screenshot build). They are built from GPL-3.0 sources (upstream + this patch); the corresponding source is this patch plus the upstream commit above. Verify with `sha1sum -c SHA1SUMS` after downloading.
