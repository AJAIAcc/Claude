package dev.aj.hermes;

import java.util.ArrayList;
import java.util.List;

/**
 * End-to-end test over a real socket, against tests/fake_server.py.
 *
 * CoreTest already covers the parsers. What only a socket can check is the
 * request {@link Net} actually builds — headers, body, the streaming flag —
 * and that a chunked SSE response is read as it arrives rather than in one
 * lump. Run with tests/live.sh.
 */
public class LiveTest {

    static int passed;
    static int failed;

    static void check(boolean cond, String what) {
        if (cond) {
            passed++;
        } else {
            failed++;
            System.out.println("FAIL: " + what);
        }
    }

    static void eq(Object got, Object want, String what) {
        boolean ok = got == null ? want == null : got.equals(want);
        if (!ok) {
            what = what + " (got <" + got + ">, want <" + want + ">)";
        }
        check(ok, what);
    }

    /** Collects a reply, and records the order the halves arrived in. */
    static final class Catch implements Net.Sink {
        final StringBuilder text = new StringBuilder();
        final StringBuilder think = new StringBuilder();
        final List<String> order = new ArrayList<String>();
        String finish;
        String error;
        int dones;

        public void delta(String t) {
            text.append(t);
            order.add("a");
        }

        public void reasoning(String t) {
            think.append(t);
            order.add("r");
        }

        public void done(String f) {
            finish = f;
            dones++;
        }

        public void failed(String m) {
            error = m;
        }
    }

    static String base;

    static Net.Params params(String model, boolean stream) {
        Net.Params p = new Net.Params();
        p.baseUrl = base;
        p.apiKey = "sk-test-key";
        p.model = model;
        p.stream = stream;
        p.temperature = 0.3;
        p.maxTokens = 128;
        return p;
    }

    static Catch ask(Net.Params p, String question) {
        Chat.Conversation c = new Chat.Conversation(1L);
        c.add(new Chat.Message(Chat.USER, question));
        Catch sink = new Catch();
        Net.chat(p, Chat.wire(c, "be brief", 0), sink, new Net.Call());
        return sink;
    }

    public static void main(String[] args) throws Exception {
        base = "http://127.0.0.1:" + args[0] + "/v1";

        // ---- streaming, with a trace whose tags straddle chunk boundaries
        Catch a = ask(params("Hermes-4-70B", true), "hello?");
        eq(a.error, null, "streaming turn had no error");
        eq(a.text.toString(), "Hello from Hermes.", "answer assembled from chunks");
        eq(a.think.toString(), "I should be brief.", "trace assembled across chunks");
        eq(a.finish, "stop", "finish reason carried through");
        eq(Integer.valueOf(a.dones), Integer.valueOf(1), "completed once");
        // The trace must arrive before the answer, not be sorted afterwards.
        check(a.order.indexOf("r") < a.order.indexOf("a"), "trace streamed before answer");
        check(a.order.size() > 3, "reply arrived in pieces, not one lump");

        // ---- the request the app actually sent
        Object last = Json.parse(get(base.replace("/v1", "") + "/last"));
        eq(Json.str(last, "authorization"), "Bearer sk-test-key", "bearer token sent");
        eq(Json.str(last, "content_type"), "application/json", "content type sent");
        eq(Json.str(last, "accept"), "text/event-stream", "SSE accept header sent");
        eq(Json.str(last, "accept_encoding"), "identity", "gzip declined while streaming");
        check(Json.str(last, "user_agent").indexOf("Hermes-Android") >= 0, "user agent sent");
        eq(Json.str(last, "body", "model"), "Hermes-4-70B", "model sent");
        eq(Json.dig(last, "body", "stream"), Boolean.TRUE, "stream flag sent");
        eq(Json.dig(last, "body", "max_tokens"), Long.valueOf(128), "max_tokens sent");
        eq(Json.str(last, "body", "messages", Integer.valueOf(0), "role"), "system",
                "system prompt first");
        eq(Json.str(last, "body", "messages", Integer.valueOf(1), "content"), "hello?",
                "question sent");

        // ---- non-streaming, including a trace in the whole reply
        Catch w = ask(params("whole", false), "hello?");
        eq(w.error, null, "non-streaming turn had no error");
        eq(w.text.toString(), "A whole answer.", "whole answer read");
        eq(w.think.toString(), "quietly", "trace split out of a whole reply");
        eq(w.finish, "stop", "finish reason from a whole reply");
        Object last2 = Json.parse(get(base.replace("/v1", "") + "/last"));
        eq(Json.dig(last2, "body", "stream"), Boolean.FALSE, "stream flag off");
        eq(Json.str(last2, "accept"), "application/json", "JSON accept header");

        // ---- a refusal, with the server's own wording kept
        Catch e = ask(params("err401", true), "hello?");
        check(e.error != null, "401 reported as an error");
        check(e.error.indexOf("401") >= 0, "401 names the status");
        check(e.error.indexOf("invalid api key") >= 0, "server's message kept");
        eq(Integer.valueOf(e.dones), Integer.valueOf(0), "no completion on failure");

        // ---- an HTML error page must not be shown raw
        Catch h = ask(params("err500html", true), "hello?");
        check(h.error != null, "502 reported");
        check(h.error.indexOf("<") < 0, "html error page not shown raw");

        // ---- an error part way through a 200
        Catch m = ask(params("midstream", true), "hello?");
        eq(m.error, "ran out of context", "mid-stream error surfaced");
        eq(m.text.toString(), "starting", "text before the error kept");
        eq(Integer.valueOf(m.dones), Integer.valueOf(0), "no completion after mid-stream error");

        // ---- a 200 that closes with nothing in it
        Catch s = ask(params("silent", true), "hello?");
        check(s.error != null, "silent stream reported as an error");
        eq(Integer.valueOf(s.dones), Integer.valueOf(0), "no completion on a silent stream");

        // ---- cancelling mid-reply
        final Net.Call call = new Net.Call();
        final Catch c = new Catch();
        final Net.Params p = params("Hermes-4-70B", true);
        Thread t = new Thread(new Runnable() {
            public void run() {
                Chat.Conversation conv = new Chat.Conversation(2L);
                conv.add(new Chat.Message(Chat.USER, "hello?"));
                Net.chat(p, Chat.wire(conv, "", 0), c, call);
            }
        });
        t.start();
        Thread.sleep(25); // let the first chunks land
        call.cancel();
        t.join(10000);
        check(!t.isAlive(), "cancel unblocked the reader");
        eq(Integer.valueOf(c.dones), Integer.valueOf(0), "cancelled: no completion");
        eq(c.error, null, "cancelled: no error reported");

        // ---- the model list
        List<String> ids = Net.models(params("Hermes-4-70B", true));
        eq(Integer.valueOf(ids.size()), Integer.valueOf(3), "three models listed");
        eq(ids.get(0), "Hermes-4-405B", "first model id");

        // ---- a base URL missing its /v1 still reaches the endpoint
        Net.Params bare = params("Hermes-4-70B", true);
        bare.baseUrl = "http://127.0.0.1:" + args[0];
        eq(Integer.valueOf(Net.models(bare).size()), Integer.valueOf(3), "bare host works");

        // ---- nothing listening
        Net.Params dead = params("Hermes-4-70B", true);
        dead.baseUrl = "http://127.0.0.1:1/v1";
        Catch d = ask(dead, "hello?");
        check(d.error != null, "a refused connection is reported");

        System.out.println(passed + " passed, " + failed + " failed");
        if (failed > 0) {
            System.exit(1);
        }
    }

    /** Minimal GET, for reading the server's record of the last request. */
    static String get(String url) throws Exception {
        java.net.HttpURLConnection c =
                (java.net.HttpURLConnection) new java.net.URL(url).openConnection();
        c.setConnectTimeout(5000);
        c.setReadTimeout(5000);
        try {
            java.io.BufferedReader r = new java.io.BufferedReader(
                    new java.io.InputStreamReader(c.getInputStream(), "UTF-8"));
            StringBuilder b = new StringBuilder();
            String line;
            while ((line = r.readLine()) != null) {
                b.append(line);
            }
            r.close();
            return b.toString();
        } finally {
            c.disconnect();
        }
    }
}
