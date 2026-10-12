# droidforge

A from-scratch Android build toolchain: **Java source → DEX → signed APK**, with no Android SDK, Gradle, d8, aapt2 or apksigner.
It was written because the build machine couldn't reach Google's servers, Maven, npm or PyPI.

## Requirements

- JDK 11+ (only `javac` is used)
- Python 3.8+ with the `cryptography` package

## Quick start

```sh
python3 -m forge new myapp com.example.myapp "My App"   # scaffold a project
python3 -m forge build myapp                            # -> myapp/build/MyApp-1.0.apk
python3 -m forge check myapp/build/MyApp-1.0.apk        # re-verify the signature
```

Project layout:

```
myapp/
  app.json        package, name, version, activity, min/target SDK, orientation, icon colours/letter
  src/**.java     your code (Java 8 language level, lambdas OK)
  libs/*.jar      optional plain-Java libraries (dexed into the app)
  assets/**       optional raw files (read with getAssets().open(...))
```

## What each piece replaces

| Module | Replaces | What it does |
|---|---|---|
| `stubs/` | `android.jar` | Stand-in framework classes (Activity, View, widgets, Canvas/Paint, dialogs, SharedPreferences…) with the real signatures and constant values, compile-time only |
| `forge/classfile.py` | – | Java `.class` parser |
| `forge/translate.py` | `d8` | JVM bytecode → Dalvik bytecode (type-flow analysis, register mapping, lambda desugaring, try/catch, switches, synchronized) |
| `forge/dalvik.py` | – | Dalvik opcode table, assembler, decoder |
| `forge/dexwriter.py` | `d8` | DEX file writer (sorted pools, map, Adler-32/SHA-1) |
| `forge/resources.py` | `aapt2` | Binary XML manifest, `resources.arsc`, adaptive and legacy launcher icons (PNG encoder) |
| `forge/apk.py` | `zipalign` + `apksigner` | Aligned zip plus APK Signature Scheme v2, and a verifier |
| `forge/dexcheck.py` | `dexdump` + verifier | Structural DEX validator, register-type checker and disassembler (`python3 -m forge.dexcheck x.dex -d`) |
| `forge/dexvm.py` | – | Tiny Dalvik interpreter used for differential testing |

## Testing

`./run_all_tests.sh` compiles each program in `tests/cases`, runs it on the real JVM, and runs our DEX in the test VM.
The outputs must match exactly.
Seven programs cover arithmetic edge cases, floats, switches, exceptions, `finally`, lambdas, inner classes, enums, `synchronized` and interfaces.

The stress test also translates about 2,600 classes of the JDK's own library and validates every method.
To run it, first extract `java.base` with `jimage` to `/tmp/jdk`.

## Limits (by design, for now)

- UI is built in Java code. XML layouts, `R.java` and string or drawable resources are not compiled. The only resources are the launcher icon, plus `assets/`.
- The framework API is a hand-written subset. To use an API that isn't there, add its exact signature to `stubs/spec_content.txt` and run `python3 stubs/build_stubs.py`.
- Java 8 language level; records and pattern switches are not supported. AndroidX, Kotlin and native `.so` libraries are not supported.
- minSdk 24 (Android 7.0+); the default targetSdk is 34. Signing is v2 only.
- Tested with a DEX validator and interpreter, not on a real device or emulator from this machine.

## Signing key — keep it

`keystore/release-key.pem` plus `release-cert.der` sign every APK.
Android only installs an update over an existing app if it's signed with the same key.
Back these files up and don't share the `.pem`.

## Installing on a phone

Copy the APK to the phone and open it. Allow "Install unknown apps" for your file manager or browser when prompted.
Play Protect may warn about an unknown developer; choose "Install anyway".
