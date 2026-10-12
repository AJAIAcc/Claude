package dev.aj.hermes;

import java.io.BufferedReader;
import java.io.IOException;
import java.io.InputStream;
import java.io.InputStreamReader;
import java.io.OutputStream;
import java.io.Reader;
import java.net.HttpURLConnection;
import java.net.MalformedURLException;
import java.net.SocketTimeoutException;
import java.net.URL;
import java.net.UnknownHostException;
import java.util.ArrayList;
import java.util.List;
import java.util.Map;

/**
 * The transport: an OpenAI-compatible {@code /chat/completions} client over
 * {@code HttpURLConnection}, which on Android is the platform's own HTTP stack.
 *
 * No Android imports, so the stream handling is tested on the desktop JVM
 * against canned streams — see {@link #consume}, which is the whole
 * SSE → reasoning-split → sink pipeline with the socket factored out.
 *
 * Everything here runs on a worker thread. Nothing in this file touches a
 * view; results leave through {@link Sink}, and the activity is responsible
 * for hopping back to the UI thread.
 */
final class Net {

    /**
     * A refusal from the server, already phrased for a person by
     * {@link #httpError}. Distinct from a transport failure so the caller can
     * show it as-is instead of re-describing it.
     */
    static final class ApiException extends IOException {
        ApiException(String message) {
            super(message);
        }
    }

    /** Where a reply is delivered, incrementally. Called on the worker thread. */
    interface Sink {
        /** Answer text. */
        void delta(String text);

        /** Reasoning-trace text, if the model emits one. */
        void reasoning(String text);

        /** Normal end. {@code finishReason} may be null. */
        void done(String finishReason);

        /** Gave up. {@code message} is fit to show a person. */
        void failed(String message);
    }

    /** Request settings, so this class needs no Android imports. */
    static final class Params {
        String baseUrl = Defaults.BASE_URL;
        String apiKey = "";
        String model = Defaults.MODEL;
        double temperature = 0.7;
        int maxTokens;
        boolean stream = true;
    }

    /**
     * A cancellation handle. The reading loop checks it between lines, and
     * {@link #cancel} also disconnects so a blocked read gives up at once
     * rather than holding the socket until the read timeout.
     */
    static final class Call {
        private volatile boolean cancelled;
        private volatile HttpURLConnection conn;

        void cancel() {
            cancelled = true;
            HttpURLConnection c = conn;
            if (c != null) {
                try {
                    c.disconnect();
                } catch (RuntimeException ignored) {
                    // disconnecting is best-effort
                }
            }
        }

        boolean cancelled() {
            return cancelled;
        }

        private void attach(HttpURLConnection c) {
            conn = c;
            if (cancelled) {
                cancel(); // cancelled while connecting
            }
        }
    }

    private static final int CONNECT_MS = 20000;
    /** Generous: this is the gap allowed between tokens, not the whole reply. */
    private static final int READ_MS = 180000;

    private Net() {
    }

    // -------------------------------------------------------------- endpoint

    /**
     * Joins a base URL and a path.
     *
     * Typing the host without {@code /v1} is the easiest mistake to make, and
     * it fails as a 404 that looks like a missing model, so a base with no
     * path of its own gets {@code /v1} added.
     */
    static String endpoint(String base, String path) {
        String b = base == null ? "" : base.trim();
        if (b.isEmpty()) {
            b = Defaults.BASE_URL;
        }
        while (b.endsWith("/")) {
            b = b.substring(0, b.length() - 1);
        }
        int scheme = b.indexOf("://");
        String afterHost = scheme < 0 ? b : b.substring(scheme + 3);
        if (afterHost.indexOf('/') < 0) {
            b = b + "/v1";
        }
        return b + path;
    }

    // ------------------------------------------------------------------ chat

    /** Runs one turn to completion, reporting through {@code sink}. */
    static void chat(Params p, List<Object> messages, Sink sink, Call call) {
        HttpURLConnection c = null;
        try {
            Map<String, Object> body = Json.map();
            body.put("model", p.model);
            body.put("messages", messages);
            body.put("stream", Boolean.valueOf(p.stream));
            body.put("temperature", Double.valueOf(p.temperature));
            if (p.maxTokens > 0) {
                body.put("max_tokens", Integer.valueOf(p.maxTokens));
            }

            c = open(p, endpoint(p.baseUrl, "/chat/completions"), "POST");
            if (p.stream) {
                c.setRequestProperty("Accept", "text/event-stream");
                // Without this the platform may ask for gzip, and a compressed
                // stream can sit in a buffer instead of arriving token by token.
                c.setRequestProperty("Accept-Encoding", "identity");
            } else {
                c.setRequestProperty("Accept", "application/json");
            }
            c.setDoOutput(true);
            call.attach(c);

            byte[] out = Json.write(body).getBytes("UTF-8");
            // Deliberately not setFixedLengthStreamingMode: with output
            // streaming on, HttpURLConnection cannot replay the request, and
            // getErrorStream() then comes back null — so a 401 would lose the
            // provider's own explanation, which is the part worth reading.
            // Request bodies here are a chat history, small enough to buffer.
            OutputStream os = c.getOutputStream();
            os.write(out);
            os.flush();
            os.close();

            int code = c.getResponseCode();
            if (call.cancelled()) {
                return;
            }
            if (code < 200 || code >= 300) {
                sink.failed(httpError(code, read(c.getErrorStream())));
                return;
            }

            InputStream in = c.getInputStream();
            Reader r = new InputStreamReader(in, "UTF-8");
            if (p.stream) {
                consume(r, sink, call);
            } else {
                whole(readAll(r), sink);
            }
        } catch (IOException e) {
            if (!call.cancelled()) {
                sink.failed(ioError(e, p.baseUrl));
            }
        } catch (RuntimeException e) {
            if (!call.cancelled()) {
                sink.failed("Something went wrong: " + e.getClass().getSimpleName());
            }
        } finally {
            if (c != null) {
                try {
                    c.disconnect();
                } catch (RuntimeException ignored) {
                    // nothing useful to do
                }
            }
        }
    }

    /**
     * Reads an SSE stream, splits out any {@code <think>} trace, and reports
     * each piece. Separated from the socket so it can be tested with a
     * {@code StringReader}.
     */
    static void consume(Reader reader, final Sink sink, Call call) throws IOException {
        BufferedReader br = new BufferedReader(reader, 8192);
        Sse sse = new Sse();
        Think think = new Think(new Think.Sink() {
            public void answer(String t) {
                sink.delta(t);
            }

            public void reasoning(String t) {
                sink.reasoning(t);
            }
        });
        String finish = null;
        boolean ended = false;
        boolean sawChunk = false;
        String line;
        while ((line = br.readLine()) != null) {
            if (call.cancelled()) {
                think.finish();
                return;
            }
            String payload = sse.line(line);
            if (payload == null) {
                continue;
            }
            if (payload.equals(Sse.DONE)) {
                ended = true;
                break;
            }
            Object chunk;
            try {
                chunk = Json.parse(payload);
            } catch (Json.Bad b) {
                continue; // a chunk we can't read is not worth failing the turn
            }
            // An error can arrive mid-stream, after a 200.
            String err = Sse.error(chunk);
            if (err != null) {
                think.finish();
                sink.failed(err);
                return;
            }
            sawChunk = true;
            String[] d = Sse.delta(chunk);
            if (d[1] != null) {
                sink.reasoning(d[1]);
            }
            if (d[0] != null) {
                think.feed(d[0]);
            }
            String f = Sse.finish(chunk);
            if (f != null) {
                finish = f;
            }
        }
        // A trailing event with no blank line after it still counts.
        String tail = sse.flush();
        if (tail != null && !tail.equals(Sse.DONE) && !ended) {
            try {
                Object chunk = Json.parse(tail);
                String[] d = Sse.delta(chunk);
                if (d[1] != null) {
                    sink.reasoning(d[1]);
                }
                if (d[0] != null) {
                    think.feed(d[0]);
                }
                if (Sse.finish(chunk) != null) {
                    finish = Sse.finish(chunk);
                }
                sawChunk = true;
            } catch (Json.Bad ignored) {
                // same as above: unreadable tail, nothing to add
            }
        }
        think.finish();
        if (call.cancelled()) {
            return;
        }
        if (!sawChunk && !ended) {
            sink.failed("The server closed the connection without sending a reply.");
            return;
        }
        sink.done(finish);
    }

    /** The non-streaming path: one JSON document holding the whole reply. */
    private static void whole(String body, Sink sink) {
        Object doc;
        try {
            doc = Json.parse(body);
        } catch (Json.Bad b) {
            sink.failed("The server's reply was not valid JSON.");
            return;
        }
        String err = Sse.error(doc);
        if (err != null) {
            sink.failed(err);
            return;
        }
        String[] d = Sse.delta(doc);
        if (d[1] != null) {
            sink.reasoning(d[1]);
        }
        if (d[0] != null) {
            // The same trace tags can appear in a non-streamed reply.
            Think t = new Think(new ThinkTo(sink));
            t.feed(d[0]);
            t.finish();
        } else {
            sink.failed("The reply contained no message.");
            return;
        }
        sink.done(Sse.finish(doc));
    }

    /** Named rather than anonymous so {@link #whole} stays readable. */
    private static final class ThinkTo implements Think.Sink {
        private final Sink sink;

        ThinkTo(Sink sink) {
            this.sink = sink;
        }

        public void answer(String t) {
            sink.delta(t);
        }

        public void reasoning(String t) {
            sink.reasoning(t);
        }
    }

    // ---------------------------------------------------------------- models

    /** Model ids the endpoint advertises. Throws so the caller can show why. */
    static List<String> models(Params p) throws IOException {
        HttpURLConnection c = null;
        try {
            c = open(p, endpoint(p.baseUrl, "/models"), "GET");
            c.setRequestProperty("Accept", "application/json");
            c.setReadTimeout(60000);
            int code = c.getResponseCode();
            if (code < 200 || code >= 300) {
                throw new ApiException(httpError(code, read(c.getErrorStream())));
            }
            Object doc;
            try {
                doc = Json.parse(readAll(new InputStreamReader(c.getInputStream(), "UTF-8")));
            } catch (Json.Bad b) {
                throw new ApiException("The model list was not valid JSON.");
            }
            List<String> ids = Sse.models(doc);
            if (ids.isEmpty()) {
                throw new ApiException("The endpoint listed no models.");
            }
            return ids;
        } finally {
            if (c != null) {
                try {
                    c.disconnect();
                } catch (RuntimeException ignored) {
                    // nothing useful to do
                }
            }
        }
    }

    // ----------------------------------------------------------------- plumbing

    private static HttpURLConnection open(Params p, String url, String method)
            throws IOException {
        URL u;
        try {
            u = new URL(url);
        } catch (MalformedURLException e) {
            throw new IOException("That base URL isn't valid: " + url);
        }
        HttpURLConnection c = (HttpURLConnection) u.openConnection();
        c.setRequestMethod(method);
        c.setConnectTimeout(CONNECT_MS);
        c.setReadTimeout(READ_MS);
        c.setUseCaches(false);
        c.setInstanceFollowRedirects(true);
        c.setRequestProperty("Content-Type", "application/json");
        c.setRequestProperty("User-Agent", "Hermes-Android/" + Defaults.VERSION);
        String key = p.apiKey == null ? "" : p.apiKey.trim();
        if (!key.isEmpty()) {
            c.setRequestProperty("Authorization", "Bearer " + key);
        }
        return c;
    }

    private static String read(InputStream in) {
        if (in == null) {
            return "";
        }
        try {
            return readAll(new InputStreamReader(in, "UTF-8"));
        } catch (IOException e) {
            return "";
        }
    }

    private static String readAll(Reader r) throws IOException {
        StringBuilder b = new StringBuilder();
        char[] buf = new char[4096];
        int n;
        // Cap it: a runaway body must not exhaust the heap.
        while ((n = r.read(buf)) > 0 && b.length() < 4 * 1024 * 1024) {
            b.append(buf, 0, n);
        }
        return b.toString();
    }

    /**
     * Turns a status code into something worth reading. The provider's own
     * message is kept when there is one, because it is usually more specific
     * than anything we could say.
     */
    static String httpError(int code, String body) {
        String detail = null;
        if (body != null && !body.trim().isEmpty()) {
            try {
                detail = Sse.error(Json.parse(body));
            } catch (Json.Bad b) {
                String t = body.trim();
                // Not JSON: an HTML error page is noise, a short line is not.
                if (t.length() <= 200 && t.indexOf('<') < 0) {
                    detail = t;
                }
            }
        }
        String head;
        if (code == 401) {
            head = "Unauthorised (401) — check the API key in Settings.";
        } else if (code == 402) {
            head = "Payment required (402) — the account may be out of credit.";
        } else if (code == 403) {
            head = "Forbidden (403) — the key may not have access to this model.";
        } else if (code == 404) {
            head = "Not found (404) — check the base URL and the model id.";
        } else if (code == 413) {
            head = "Too large (413) — shorten the conversation or lower the history limit.";
        } else if (code == 429) {
            head = "Rate limited (429) — wait a moment and send it again.";
        } else if (code >= 500) {
            head = "The server had a problem (" + code + ").";
        } else {
            head = "The request was refused (" + code + ").";
        }
        return detail == null || detail.isEmpty() ? head : head + "\n" + detail;
    }

    /** Transport failures, named in terms of what the person can do about them. */
    static String ioError(IOException e, String base) {
        if (e instanceof UnknownHostException) {
            return "Can't find " + host(base) + ". Check the connection and the base URL.";
        }
        if (e instanceof SocketTimeoutException) {
            return "Timed out waiting for the server. It may be busy — try again.";
        }
        String m = e.getMessage();
        if (m != null && m.indexOf("CLEARTEXT") >= 0) {
            return "This build only allows HTTPS. Use an https:// base URL.";
        }
        if (e.getClass().getName().indexOf("SSL") >= 0) {
            return "The secure connection failed: " + (m == null ? "SSL error" : m);
        }
        return m == null || m.isEmpty() ? "The connection failed." : m;
    }

    private static String host(String url) {
        String s = url == null ? "" : url.trim();
        int i = s.indexOf("://");
        if (i >= 0) {
            s = s.substring(i + 3);
        }
        int slash = s.indexOf('/');
        if (slash >= 0) {
            s = s.substring(0, slash);
        }
        return s.isEmpty() ? "the server" : s;
    }

    /** Model ids worth offering before the endpoint has been asked. */
    static List<String> suggestions() {
        List<String> l = new ArrayList<String>();
        for (int i = 0; i < Defaults.MODELS.length; i++) {
            l.add(Defaults.MODELS[i]);
        }
        return l;
    }
}
