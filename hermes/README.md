# Hermes for Android

A native Android chat client for **Hermes**, the Nous Research model family, built with
the `droidforge` toolchain in this repository — no Android SDK, no Gradle, no AndroidX,
no Kotlin. Java source in, signed APK out.

```
hermes/
  app.json                  package, version, permissions, launcher icon
  src/dev/aj/hermes/*.java  the app (12 files, ~3,500 lines)
  res/values/strings.xml    the app label
  tests/run.sh              unit tests, on the desktop JVM
  tests/live.sh             end-to-end test over a real socket
  build/Hermes-1.0.apk      the signed, installable result
```

## What it does

- **Streams replies token by token** over server-sent events, with a **Stop** button
  that keeps whatever text had already arrived.
- **Separates Hermes's reasoning from its answer.** Hermes 4 is a hybrid reasoner: in
  thinking mode the trace arrives inline, wrapped in `<think>…</think>`. The app pulls
  it out and shows it in a collapsible panel instead of leaving it in the reply. It also
  reads a separated `reasoning_content` field, which is how some gateways deliver the
  same thing.
- **Renders replies as Markdown** — headings, bullets, block quotes, and code in a
  monospaced card that scrolls sideways rather than wrapping.
- **Keeps conversations** on the device, switchable from a list, deletable by long press.
- **Settings**: API key, base URL, model, system prompt (with a one-tap deep-thinking
  preset), temperature, max tokens, and how much history to re-send.
- **Asks the endpoint which models it has**, via `GET /v1/models`, listing Hermes models
  first — useful on a gateway whose catalogue runs to hundreds.

## Pointing it at a server

It speaks the OpenAI chat-completions dialect, so it works against Nous's hosted API, a
gateway, or anything else compatible. Out of the box:

| Setting | Default |
|---|---|
| Base URL | `https://inference-api.nousresearch.com/v1` |
| Model | `Hermes-4-70B` |
| Auth | `Authorization: Bearer <your key>` |

Open **Settings**, paste a key, and send a message. A base URL with no path of its own
gets `/v1` appended, since leaving it off is the easy mistake and it fails as a 404 that
looks like a missing model.

> **Worth knowing:** the default endpoint and the model ids were taken from Nous's
> published API surface, but the build machine's network policy blocked
> `nousresearch.com`, so they could not be confirmed against the live service from here.
> That is exactly why all three are editable rather than compiled in — if a path moves or
> a model is renamed, fix it in Settings, no rebuild. Verify the current ids with the
> **Model → Ask the endpoint for its list** option, which is authoritative.

## Building

```sh
cd droidforge
python3 -m forge build ../hermes          # -> ../hermes/build/Hermes-1.0.apk
python3 -m forge check ../hermes/build/Hermes-1.0.apk
```

Requirements: JDK 11+ (only `javac`) and Python 3.8+ with `cryptography`.

**The signing key is not in this repository.** `droidforge/keystore/` is excluded by
`.gitignore` because `release-key.pem` is a private key and committing it would publish
it. Copy that directory back from your toolchain zip before building. It matters: Android
only installs an update over an existing app if the update carries the same signing key,
so if `forge` generates a fresh one, the APK will refuse to install over a previous
version and you would have to uninstall first — losing the stored conversations.

## Installing

Copy the APK to the phone and open it. Allow "install unknown apps" for your file manager
or browser when asked; Play Protect will warn about an unknown developer, so choose
"install anyway". Needs Android 7.0 or newer.

## Tests

```sh
hermes/tests/run.sh      # 177 checks, desktop JVM, no network
hermes/tests/live.sh     # 41 checks against a local stand-in endpoint
droidforge/run_all_tests.sh   # the toolchain's own self-test
```

`run.sh` compiles the Android-free half of the app on the desktop JVM and exercises the
JSON reader and writer, SSE framing, the `<think>` splitter, the Markdown parser, the
conversation store, URL joining and the error messages. The parts worth testing hardest
are the ones a phone-only bug would be most expensive to find:

- The JSON parser is total — every malformed input is a `Json.Bad`, including input
  nested deeply enough to overflow the stack, so a broken reply cannot crash the UI.
- The reasoning splitter is fed a stream **one character at a time**, because `<think>`
  really does arrive as `"<thi"` then `"nk>"`, and a chunk ending in `"<"` may or may not
  be the start of a tag.
- A mid-stream error after a `200`, a stream that closes silently, and a cancellation all
  have to behave; each has a test.

`live.sh` runs a stand-in endpoint on `127.0.0.1` (`tests/fake_server.py`) and drives the
real `HttpURLConnection` against it, asserting on the request the app actually builds —
headers, body, streaming flag — and on a chunked response arriving in pieces rather than
one lump. It also covers a 401 with a provider message, an HTML error page, a mid-stream
failure, and cancelling a reply in flight.

## How it is put together

| File | What it holds |
|---|---|
| `Json.java` | JSON reader and writer. `org.json` is in neither the JDK nor the stub android.jar, so the wire format is done by hand |
| `Sse.java` | Server-sent-event framing, and pulling deltas, errors and model lists out of a chunk |
| `Think.java` | The `<think>…</think>` splitter, written for a token stream |
| `Net.java` | The HTTP client: streaming and whole-reply requests, cancellation, model listing, error wording |
| `Chat.java` | Conversations and messages, their stored form and their wire form |
| `Store.java` | The conversation file, written via a temporary file and a rename |
| `Config.java` | Settings, in the app's private `SharedPreferences` |
| `Markdown.java` | Reply text to a list of blocks |
| `Ui.java` | Colours and view factories |
| `MainActivity.java` | The three screens, the streaming loop, the dialogs |
| `Defaults.java` | Where it points before anything is configured |

Three decisions that are not obvious from the code:

**Replies are redrawn on a 60 ms timer, not per token.** A `setText` per token forces a
layout pass per token, which drops frames. Deltas accumulate in a buffer on the worker
thread; the UI thread drains it on a timer. The Markdown pass runs once at the end, when
the text has stopped moving — while streaming, the bubble is plain text.

**The request body is not sent with `setFixedLengthStreamingMode`.** With output streaming
on, `HttpURLConnection` cannot replay the request and `getErrorStream()` returns null — so
a 401, the likeliest failure of all, would lose the provider's own explanation of what is
wrong with the key. This was found by the end-to-end test, not by reading the docs.

**The interface is light.** At minSdk 24 the platform theme is `DeviceDefault.Light`, so
alert dialogs and the keyboard draw for a light background, and there is no AppCompat here
to restyle them. A dark chat window under light system dialogs looks broken.

## Limits

- **HTTPS only.** Android blocks cleartext HTTP for an app targeting SDK 28+ unless the
  manifest says otherwise, and `android:usesCleartextTraffic` is not in droidforge's
  verified attribute table — that file refuses to guess a resource id rather than risk a
  silent runtime failure, which is the right call. So a local `http://` model server needs
  that attribute added to `forge/resources.py` (after checking the id against a decoded
  manifest) before it will work. Settings warns if the base URL is not HTTPS.
- **No inline bold or italic.** The stub framework has no `Spannable`, so there is no way
  to style a run of characters inside one `TextView`. Block structure is real — headings,
  bullets, code cards — but inline `**markers**` are stripped to their text rather than
  shown raw.
- **The API key is stored unencrypted** in the app's private `SharedPreferences`. That is
  the same protection the platform gives its own accounts, and other apps cannot read it,
  but it is readable on a rooted phone or an unlocked one. There is no passphrase prompt.
- **No streaming of tool calls, images or attachments.** Text in, text out.
- **Not run on a real device from this build machine.** The toolchain validates its own
  output with a structural DEX validator, a register-type checker and a small Dalvik
  interpreter — the APK here passes all three and its signature verifies — but no emulator
  or phone was available here, so the first run on real hardware is still the first run.
