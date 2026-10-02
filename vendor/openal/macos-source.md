# macOS OpenAL Soft library

`libopenal.1.dylib` was manually built from unmodified OpenAL Soft 1.25.2
source on 2026-10-02.

- Architectures: universal2, arm64 and x86_64.
- Minimum macOS: 11.0 (Big Sur), checked in both slices' `LC_BUILD_VERSION`.
- Toolchain: Apple clang 21.0.0 (clang-2100.3.34.2), macOS SDK 27.0, CMake.
- Source: https://openal-soft.org/openal-releases/openal-soft-1.25.2.tar.bz2
- Source SHA-256: `1dbaac44e7579d5bc8847ca8db4b2e8b9fd3961041f35ee20def4958301e1089`.
- Bundled dylib SHA-256: `01add8cd841c040b6f2500a72c491966d6598e7628ce108e5e25f5d6bc23db5c`.

Both slices link only macOS system libraries/frameworks. The install name is
`@rpath/libopenal.1.dylib`. CoreAudio, null and wave backends are included.
Default HRTF data is embedded; the game still disables HRTF. No third-party
audio dependency is needed. C++20 modules use upstream detection defaults.

## Rebuilding

Extract the source archive, then from its parent directory:

```sh
for arch in arm64 x86_64; do
    cmake -S openal-soft-1.25.2 -B "openal-build-$arch" \
        -DCMAKE_BUILD_TYPE=Release -DCMAKE_OSX_ARCHITECTURES="$arch" \
        -DCMAKE_OSX_DEPLOYMENT_TARGET=11.0 \
        -DCMAKE_C_COMPILER=/usr/bin/clang -DCMAKE_CXX_COMPILER=/usr/bin/clang++ \
        -DCMAKE_INSTALL_NAME_DIR=@rpath -DCMAKE_DISABLE_FIND_PACKAGE_PkgConfig=ON \
        -DHAVE_WFUNCTION_EFFECTS=OFF \
        -DALSOFT_UTILS=OFF -DALSOFT_EXAMPLES=OFF -DALSOFT_TESTS=OFF \
        -DALSOFT_BACKEND_COREAUDIO=ON \
        -DALSOFT_BACKEND_PORTAUDIO=OFF -DALSOFT_BACKEND_PULSEAUDIO=OFF \
        -DALSOFT_BACKEND_PIPEWIRE=OFF
    cmake --build "openal-build-$arch" --parallel 4
done
lipo -create openal-build-arm64/libopenal.1.25.2.dylib \
    openal-build-x86_64/libopenal.1.25.2.dylib -output libopenal.1.dylib
install_name_tool -id @rpath/libopenal.1.dylib libopenal.1.dylib
codesign --force --sign - libopenal.1.dylib
```

`HAVE_WFUNCTION_EFFECTS=OFF` disables a compiler diagnostic that upstream
enables as an error: SDK 27 adds a `nonblocking` callback annotation that
1.25.2's CoreAudio lambdas lack. No upstream source patch is applied.
Rebuild hashes may differ with toolchain, build path and local signature.

Upstream `COPYING` and `LICENSE-pffft` match the existing `license.txt` and
`license-pffft.txt` byte-for-byte. `license-fmt.txt` is the license of statically
included fmt 11.2.0; `license-gsl.txt` covers the included Microsoft GSL headers.
The macOS compiler packages all four licenses.
