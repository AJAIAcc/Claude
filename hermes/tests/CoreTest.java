package dev.aj.hermes;

import java.util.ArrayList;
import java.util.List;
import java.util.Map;

/**
 * Desktop tests for the parts with no Android imports. Run with tests/run.sh.
 *
 * The wire format and the streaming splitter are where a phone-only bug would
 * be most expensive to find, so they are tested here on the JVM instead.
 */
public class CoreTest {

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

    public static void main(String[] args) throws Exception {
        json();
        jsonBad();
        sse();
        think();
        markdown();
        chat();
        endpoint();
        errors();
        stream();
        System.out.println(passed + " passed, " + failed + " failed");
        if (failed > 0) {
            System.exit(1);
        }
    }

    // ------------------------------------------------------------------ json

    static void json() throws Exception {
        Object o = Json.parse("{\"a\":1,\"b\":[true,false,null],\"c\":{\"d\":\"x\"}}");
        eq(Json.dig(o, "a"), Long.valueOf(1), "int parses as long");
        eq(Json.str(o, "c", "d"), "x", "nested string");
        eq(Json.list(o, "b").size(), Integer.valueOf(3), "array length");
        eq(Json.dig(o, "b", Integer.valueOf(0)), Boolean.TRUE, "array index");
        eq(Json.dig(o, "b", Integer.valueOf(2)), null, "null element");

        // Absent / wrong-shape lookups must be null, not an exception.
        eq(Json.dig(o, "nope"), null, "missing key");
        eq(Json.dig(o, "a", "deeper"), null, "index into a scalar");
        eq(Json.dig(o, "b", Integer.valueOf(9)), null, "index past end");
        eq(Json.str(o, "a"), null, "number is not a string");
        eq(Json.list(o, "nope").size(), Integer.valueOf(0), "missing list is empty");

        eq(Json.parse("  3.5 "), Double.valueOf(3.5), "real");
        eq(Json.parse("-2"), Long.valueOf(-2), "negative");
        eq(Json.parse("1e3"), Double.valueOf(1000.0), "exponent");
        eq(Json.parse("\"\\u00e9\\n\\t\\\"\\\\\""), "\u00e9\n\t\"\\", "escapes");
        eq(Json.parse("\"\\ud83d\\ude00\""), "\ud83d\ude00", "surrogate pair");
        eq(Json.parse("{}") instanceof Map, Boolean.TRUE, "empty object");
        eq(Json.list(Json.parse("[]")).size(), Integer.valueOf(0), "empty array");

        // Round trip, including the characters that break naive encoders.
        Map<String, Object> m = Json.map();
        m.put("s", "line\nbreak \"quoted\" back\\slash \u0001 \u2028");
        m.put("n", Long.valueOf(7));
        m.put("d", Double.valueOf(0.25));
        m.put("whole", Double.valueOf(3.0));
        m.put("t", Boolean.TRUE);
        m.put("z", null);
        List<Object> inner = new ArrayList<Object>();
        inner.add("a");
        inner.add(Long.valueOf(2));
        m.put("l", inner);
        String text = Json.write(m);
        check(text.indexOf("\\u0001") >= 0, "control char escaped");
        check(text.indexOf("\\u2028") >= 0, "line separator escaped");
        eq(text.indexOf("3.0"), Integer.valueOf(-1), "whole double written as integer");
        Object back = Json.parse(text);
        eq(Json.str(back, "s"), m.get("s"), "string survives round trip");
        eq(Json.dig(back, "n"), Long.valueOf(7), "number survives");
        eq(Json.dig(back, "d"), Double.valueOf(0.25), "fraction survives");
        eq(Json.dig(back, "l", Integer.valueOf(0)), "a", "list survives");
        eq(Json.dig(back, "z"), null, "null survives");
        eq(Json.write("a\"b"), "\"a\\\"b\"", "bare string escaping");
    }

    static void jsonBad() {
        String[] bad = {"", "{", "{\"a\"}", "{\"a\":}", "[1,]", "tru", "\"unterminated",
                        "{\"a\":1}x", "\"\\q\"", "\"\\u12\"", "--1", "{1:2}"};
        for (int i = 0; i < bad.length; i++) {
            boolean threw = false;
            try {
                Json.parse(bad[i]);
            } catch (Json.Bad b) {
                threw = true;
            } catch (RuntimeException r) {
                check(false, "parse of <" + bad[i] + "> threw " + r.getClass().getName()
                        + " instead of Json.Bad");
                continue;
            }
            check(threw, "rejects <" + bad[i] + ">");
        }
        // Deep nesting must be refused rather than overflowing the stack.
        StringBuilder deep = new StringBuilder();
        for (int i = 0; i < 400; i++) {
            deep.append('[');
        }
        boolean threw = false;
        try {
            Json.parse(deep.toString());
        } catch (Json.Bad b) {
            threw = true;
        } catch (StackOverflowError e) {
            check(false, "deep nesting overflowed the stack");
            return;
        }
        check(threw, "refuses deeply nested input");
        boolean nullThrew = false;
        try {
            Json.parse(null);
        } catch (Json.Bad b) {
            nullThrew = true;
        }
        check(nullThrew, "null input is Bad, not NPE");
    }

    // ------------------------------------------------------------------- sse

    static void sse() throws Exception {
        Sse s = new Sse();
        eq(s.line("data: {\"a\":1}"), null, "data line waits for the blank line");
        eq(s.line(""), "{\"a\":1}", "blank line completes the event");
        eq(s.line(": keep-alive"), null, "comment ignored");
        eq(s.line("event: message"), null, "non-data field ignored");
        eq(s.line("data: one\r"), null, "CR stripped");
        eq(s.line("data: two"), null, "second data line held");
        eq(s.line(""), "one\ntwo", "multiple data lines join with newline");
        eq(s.line("data: [DONE]"), Sse.DONE, "terminator recognised");
        eq(s.line("data:tight"), null, "no space after colon");
        eq(s.flush(), "tight", "flush completes a pending event");
        eq(s.flush(), null, "flush with nothing pending");
        eq(s.line(null), null, "null line is harmless");

        // Streaming chunk shape.
        Object chunk = Json.parse("{\"choices\":[{\"delta\":{\"content\":\"hi\"},"
                + "\"finish_reason\":null}]}");
        eq(Sse.delta(chunk)[0], "hi", "delta content");
        eq(Sse.delta(chunk)[1], null, "no reasoning field");
        eq(Sse.finish(chunk), null, "not finished yet");

        Object last = Json.parse("{\"choices\":[{\"delta\":{},\"finish_reason\":\"stop\"}]}");
        eq(Sse.finish(last), "stop", "finish reason");

        // Non-streaming shape parses through the same extractor.
        Object whole = Json.parse("{\"choices\":[{\"message\":{\"role\":\"assistant\","
                + "\"content\":\"full\"}}]}");
        eq(Sse.delta(whole)[0], "full", "message content");

        // Separated reasoning, on either field name.
        Object r1 = Json.parse("{\"choices\":[{\"delta\":{\"reasoning_content\":\"why\"}}]}");
        eq(Sse.delta(r1)[1], "why", "reasoning_content");
        Object r2 = Json.parse("{\"choices\":[{\"delta\":{\"reasoning\":\"why2\"}}]}");
        eq(Sse.delta(r2)[1], "why2", "reasoning");

        // Junk must not throw.
        eq(Sse.delta(Json.parse("{}"))[0], null, "empty object yields no delta");
        eq(Sse.delta(Json.parse("[]"))[0], null, "array yields no delta");
        eq(Sse.finish(Json.parse("{}")), null, "no finish reason in empty object");

        // Error bodies, in each shape seen in the wild.
        eq(Sse.error(Json.parse("{\"error\":{\"message\":\"bad key\"}}")), "bad key", "nested error");
        eq(Sse.error(Json.parse("{\"error\":\"flat\"}")), "flat", "flat error");
        eq(Sse.error(Json.parse("{\"message\":\"m\"}")), "m", "message error");
        eq(Sse.error(Json.parse("{\"detail\":\"d\"}")), "d", "detail error");
        eq(Sse.error(Json.parse("{}")), null, "no error message");

        // Model listings.
        List<String> ids = Sse.models(Json.parse("{\"data\":[{\"id\":\"Hermes-4-70B\"},"
                + "{\"id\":\"Hermes-4-405B\"},{\"id\":\"Hermes-4-70B\"}]}"));
        eq(ids.size(), Integer.valueOf(2), "duplicate ids collapse");
        eq(ids.get(0), "Hermes-4-70B", "first model id");
        eq(Sse.models(Json.parse("[\"a\",\"b\"]")).size(), Integer.valueOf(2), "bare array of ids");
        eq(Sse.models(Json.parse("{}")).size(), Integer.valueOf(0), "no models");
    }

    // ----------------------------------------------------------------- think

    /** Collects both halves of a split so a test can assert on them. */
    static final class Pen implements Think.Sink {
        final StringBuilder a = new StringBuilder();
        final StringBuilder r = new StringBuilder();

        public void answer(String t) {
            a.append(t);
        }

        public void reasoning(String t) {
            r.append(t);
        }
    }

    static void think() {
        Pen p = new Pen();
        Think t = new Think(p);
        t.feed("<think>weighing it up</think>The answer is 4.");
        t.finish();
        eq(p.r.toString(), "weighing it up", "trace extracted");
        eq(p.a.toString(), "The answer is 4.", "answer extracted");
        check(t.sawReasoning(), "reasoning was seen");
        check(!t.thinking(), "not thinking at the end");

        // The real case: tags arrive split across chunks, one character at a time.
        String whole = "pre<think>abc</think>post<think>d</think>tail";
        Pen q = new Pen();
        Think u = new Think(q);
        for (int i = 0; i < whole.length(); i++) {
            u.feed(whole.substring(i, i + 1));
        }
        u.finish();
        eq(q.a.toString(), "preposttail", "answer survives char-by-char feed");
        eq(q.r.toString(), "abcd", "trace survives char-by-char feed");

        // Awkward chunk boundaries inside the tags.
        Pen v = new Pen();
        Think w = new Think(v);
        w.feed("x<thi");
        w.feed("nk>y</thi");
        w.feed("nk>z");
        w.finish();
        eq(v.a.toString(), "xz", "answer across split tags");
        eq(v.r.toString(), "y", "trace across split tags");

        // Text that merely looks like the start of a tag must survive.
        Pen lt = new Pen();
        Think ltt = new Think(lt);
        ltt.feed("a < b and 3<4");
        ltt.finish();
        eq(lt.a.toString(), "a < b and 3<4", "bare less-than kept");
        check(!ltt.sawReasoning(), "no reasoning seen");

        // A held-back suffix that never completes must still be released.
        Pen h = new Pen();
        Think hh = new Think(h);
        hh.feed("done<thin");
        eq(h.a.toString(), "done", "partial tag held back while streaming");
        hh.finish();
        eq(h.a.toString(), "done<thin", "held suffix released at finish");

        // Unclosed trace: everything after the tag is reasoning.
        Pen o = new Pen();
        Think oo = new Think(o);
        oo.feed("<think>never closed");
        oo.finish();
        eq(o.r.toString(), "never closed", "unclosed trace stays reasoning");
        eq(o.a.toString(), "", "no answer when unclosed");
        check(oo.thinking(), "still thinking when unclosed");

        // Empty and null feeds.
        Pen e = new Pen();
        Think ee = new Think(e);
        ee.feed("");
        ee.feed(null);
        ee.finish();
        eq(e.a.toString(), "", "empty feed produces nothing");
    }

    // -------------------------------------------------------------- markdown

    static void markdown() {
        List<Markdown.Block> bs = Markdown.parse("# Title\n\nSome *text* with `code`.\n\n"
                + "```java\nint x = 1;\n```\n\n- one\n- two\n\n> quoted\n");
        eq(bs.get(0).kind, Integer.valueOf(Markdown.HEADING), "heading block");
        eq(bs.get(0).text, "Title", "heading text");
        eq(bs.get(1).kind, Integer.valueOf(Markdown.PARAGRAPH), "paragraph block");
        eq(bs.get(1).text, "Some text with code.", "inline markers stripped");
        eq(bs.get(2).kind, Integer.valueOf(Markdown.CODE), "code block");
        eq(bs.get(2).text, "int x = 1;", "code kept verbatim");
        eq(bs.get(2).lang, "java", "code language");
        eq(bs.get(3).kind, Integer.valueOf(Markdown.BULLET), "bullet block");
        eq(bs.get(3).text, "one", "first bullet");
        eq(bs.get(4).text, "two", "second bullet");
        eq(bs.get(5).kind, Integer.valueOf(Markdown.QUOTE), "quote block");
        eq(bs.get(5).text, "quoted", "quote text");

        // An unterminated fence (still streaming) must render as code, not vanish.
        List<Markdown.Block> open = Markdown.parse("```\nhalf written");
        eq(open.size(), Integer.valueOf(1), "one block from an open fence");
        eq(open.get(0).kind, Integer.valueOf(Markdown.CODE), "open fence is code");
        eq(open.get(0).text, "half written", "open fence content");

        // Code must not have its contents mangled as markdown.
        List<Markdown.Block> keep = Markdown.parse("```\na * b * c\n**not bold**\n```");
        eq(keep.get(0).text, "a * b * c\n**not bold**", "code is verbatim");

        eq(Markdown.parse("").size(), Integer.valueOf(0), "empty input, no blocks");
        eq(Markdown.parse("   \n\n  ").size(), Integer.valueOf(0), "blank input, no blocks");

        // Numbered lists keep their marker so the order is still readable.
        List<Markdown.Block> num = Markdown.parse("1. first\n2. second");
        eq(num.get(0).kind, Integer.valueOf(Markdown.BULLET), "numbered item is a bullet");
        eq(num.get(0).text, "1. first", "number retained");

        eq(Markdown.inline("**bold** and __also__ and *em* and `c` and ~~no~~"),
                "bold and also and em and c and ~~no~~", "inline cleanup");
        eq(Markdown.inline("a_b_c"), "a_b_c", "underscores inside a word are left alone");
        eq(Markdown.inline("2 * 3 * 4"), "2 * 3 * 4", "lone asterisks are left alone");
    }

    // ------------------------------------------------------------------ chat

    static void chat() throws Exception {
        Chat.Conversation c = new Chat.Conversation(5L);
        c.add(new Chat.Message(Chat.USER, "Hello there"));
        c.add(new Chat.Message(Chat.ASSISTANT, "Hi", "because"));
        eq(c.title(), "Hello there", "title comes from the first user message");
        eq(c.messages.size(), Integer.valueOf(2), "two messages");

        // Round trip through the stored form.
        List<Chat.Conversation> one = new ArrayList<Chat.Conversation>();
        one.add(c);
        String text = Chat.save(one);
        List<Chat.Conversation> back = Chat.load(text);
        eq(back.size(), Integer.valueOf(1), "one conversation restored");
        eq(back.get(0).id, Long.valueOf(5L), "id restored");
        eq(back.get(0).messages.size(), Integer.valueOf(2), "messages restored");
        eq(back.get(0).messages.get(1).text, "Hi", "answer restored");
        eq(back.get(0).messages.get(1).reasoning, "because", "trace restored");
        eq(back.get(0).messages.get(0).role, Chat.USER, "role restored");

        // Corrupt or empty stores must come back empty, not crash.
        eq(Chat.load("not json").size(), Integer.valueOf(0), "garbage store is empty");
        eq(Chat.load("").size(), Integer.valueOf(0), "empty store is empty");
        eq(Chat.load(null).size(), Integer.valueOf(0), "absent store is empty");
        eq(Chat.load("{\"conversations\":[{}]}").size(), Integer.valueOf(1),
                "a conversation with no fields still loads");

        // A long first line is trimmed for the list.
        Chat.Conversation d = new Chat.Conversation(6L);
        d.add(new Chat.Message(Chat.USER,
                "This is a really quite long opening question that will not fit in a list row"));
        check(d.title().length() <= 44, "long title trimmed");
        eq(new Chat.Conversation(7L).title(), "New chat", "untitled conversation");

        // The request payload: system prompt first, traces never sent back.
        Chat.Conversation e = new Chat.Conversation(8L);
        e.add(new Chat.Message(Chat.USER, "q"));
        e.add(new Chat.Message(Chat.ASSISTANT, "a", "secret trace"));
        List<Object> wire = Chat.wire(e, "be brief", 0);
        eq(wire.size(), Integer.valueOf(3), "system prompt prepended");
        eq(Json.str(wire.get(0), "role"), "system", "system first");
        eq(Json.str(wire.get(0), "content"), "be brief", "system content");
        eq(Json.str(wire.get(2), "content"), "a", "assistant content sent");
        eq(Json.dig(wire.get(2), "reasoning"), null, "trace not sent back");
        eq(Chat.wire(e, "", 0).size(), Integer.valueOf(2), "no system prompt, no system message");

        // History trimming keeps the most recent turns.
        Chat.Conversation f = new Chat.Conversation(9L);
        for (int i = 0; i < 10; i++) {
            f.add(new Chat.Message(Chat.USER, "m" + i));
        }
        List<Object> trimmed = Chat.wire(f, "", 4);
        eq(trimmed.size(), Integer.valueOf(4), "history trimmed to the cap");
        eq(Json.str(trimmed.get(3), "content"), "m9", "newest kept");
        eq(Json.str(trimmed.get(0), "content"), "m6", "oldest dropped");

        // A failed turn must not be replayed to the model, or stored.
        Chat.Conversation g = new Chat.Conversation(10L);
        g.add(new Chat.Message(Chat.USER, "q"));
        Chat.Message boom = new Chat.Message(Chat.ASSISTANT, "Rate limited (429)");
        boom.failed = true;
        g.add(boom);
        eq(Chat.wire(g, "", 0).size(), Integer.valueOf(1), "failed turn not sent");
        List<Chat.Conversation> gl = new ArrayList<Chat.Conversation>();
        gl.add(g);
        eq(Chat.load(Chat.save(gl)).get(0).messages.size(), Integer.valueOf(1),
                "failed turn not stored");
    }

    // -------------------------------------------------------------- endpoint

    static void endpoint() {
        eq(Net.endpoint("https://inference-api.nousresearch.com/v1", "/chat/completions"),
                "https://inference-api.nousresearch.com/v1/chat/completions", "base with /v1");
        eq(Net.endpoint("https://inference-api.nousresearch.com", "/models"),
                "https://inference-api.nousresearch.com/v1/models", "bare host gains /v1");
        eq(Net.endpoint("https://x.com/v1/", "/models"), "https://x.com/v1/models",
                "trailing slash dropped");
        eq(Net.endpoint("https://x.com/v1///", "/models"), "https://x.com/v1/models",
                "several trailing slashes dropped");
        eq(Net.endpoint("  https://x.com/openai/v1  ", "/models"),
                "https://x.com/openai/v1/models", "a path of its own is left alone");
        eq(Net.endpoint("", "/models"), Defaults.BASE_URL + "/models", "empty falls back");
        eq(Net.endpoint(null, "/models"), Defaults.BASE_URL + "/models", "null falls back");
        eq(Net.endpoint("http://10.0.0.5:8080", "/models"), "http://10.0.0.5:8080/v1/models",
                "host and port gain /v1");
    }

    static void errors() {
        check(Net.httpError(401, "").indexOf("401") >= 0, "401 names the code");
        check(Net.httpError(401, "").toLowerCase().indexOf("key") >= 0, "401 mentions the key");
        check(Net.httpError(401, "{\"error\":{\"message\":\"bad key\"}}").indexOf("bad key") >= 0,
                "provider message kept");
        check(Net.httpError(404, "").indexOf("model") >= 0, "404 mentions the model id");
        check(Net.httpError(429, "").indexOf("429") >= 0, "429 names the code");
        check(Net.httpError(503, "").indexOf("503") >= 0, "5xx names the code");
        // An HTML error page is noise; a short plain line is not.
        check(Net.httpError(500, "<html><body>Bad Gateway</body></html>").indexOf("<") < 0,
                "html body dropped");
        check(Net.httpError(400, "model not loaded").indexOf("model not loaded") >= 0,
                "short plain body kept");
        check(Net.ioError(new java.net.UnknownHostException("x"),
                "https://api.example.com/v1").indexOf("api.example.com") >= 0,
                "unknown host names the host");
        check(Net.ioError(new java.net.SocketTimeoutException(), "").toLowerCase()
                .indexOf("timed out") >= 0, "timeout explained");
        check(Net.ioError(new java.io.IOException("CLEARTEXT communication not permitted"), "")
                .indexOf("HTTPS") >= 0, "cleartext explained");
    }

    // ---------------------------------------------------------------- stream

    /** Collects everything a run of {@link Net#consume} reports. */
    static final class Catch implements Net.Sink {
        final StringBuilder text = new StringBuilder();
        final StringBuilder think = new StringBuilder();
        String finish;
        String error;
        int dones;

        public void delta(String t) {
            text.append(t);
        }

        public void reasoning(String t) {
            think.append(t);
        }

        public void done(String f) {
            finish = f;
            dones++;
        }

        public void failed(String m) {
            error = m;
        }
    }

    static Catch run(String wire) throws Exception {
        Catch c = new Catch();
        Net.consume(new java.io.StringReader(wire), c, new Net.Call());
        return c;
    }

    static void stream() throws Exception {
        Catch a = run("data: {\"choices\":[{\"delta\":{\"content\":\"Hel\"}}]}\n\n"
                + "data: {\"choices\":[{\"delta\":{\"content\":\"lo\"}}]}\n\n"
                + "data: {\"choices\":[{\"delta\":{},\"finish_reason\":\"stop\"}]}\n\n"
                + "data: [DONE]\n\n");
        eq(a.text.toString(), "Hello", "deltas concatenate");
        eq(a.finish, "stop", "finish reason reported");
        eq(Integer.valueOf(a.dones), Integer.valueOf(1), "done reported once");
        eq(a.error, null, "no error");

        // CRLF framing, as some gateways emit.
        Catch crlf = run("data: {\"choices\":[{\"delta\":{\"content\":\"x\"}}]}\r\n\r\n"
                + "data: [DONE]\r\n\r\n");
        eq(crlf.text.toString(), "x", "CRLF stream reads");

        // A trace split across chunks, mid-tag, the way it really arrives.
        Catch t = run("data: {\"choices\":[{\"delta\":{\"content\":\"<thi\"}}]}\n\n"
                + "data: {\"choices\":[{\"delta\":{\"content\":\"nk>why</think>\"}}]}\n\n"
                + "data: {\"choices\":[{\"delta\":{\"content\":\"Because.\"}}]}\n\n"
                + "data: [DONE]\n\n");
        eq(t.think.toString(), "why", "trace split across chunks");
        eq(t.text.toString(), "Because.", "answer after the trace");

        // Reasoning on its own field instead.
        Catch r = run("data: {\"choices\":[{\"delta\":{\"reasoning_content\":\"hmm\"}}]}\n\n"
                + "data: {\"choices\":[{\"delta\":{\"content\":\"4\"}}]}\n\n"
                + "data: [DONE]\n\n");
        eq(r.think.toString(), "hmm", "separated reasoning field");
        eq(r.text.toString(), "4", "answer alongside it");

        // Keep-alive comments and unknown fields must not disturb the stream.
        Catch k = run(": ping\n\nevent: message\ndata: {\"choices\":[{\"delta\":"
                + "{\"content\":\"ok\"}}]}\n\nid: 7\n\ndata: [DONE]\n\n");
        eq(k.text.toString(), "ok", "comments and fields ignored");

        // An unreadable chunk is skipped, not fatal.
        Catch j = run("data: not json\n\ndata: {\"choices\":[{\"delta\":{\"content\":\"y\"}}]}\n\n"
                + "data: [DONE]\n\n");
        eq(j.text.toString(), "y", "bad chunk skipped");
        eq(j.error, null, "bad chunk is not an error");

        // An error after a 200 must surface and stop the turn.
        Catch e = run("data: {\"choices\":[{\"delta\":{\"content\":\"a\"}}]}\n\n"
                + "data: {\"error\":{\"message\":\"context length exceeded\"}}\n\n");
        eq(e.error, "context length exceeded", "mid-stream error surfaces");
        eq(Integer.valueOf(e.dones), Integer.valueOf(0), "no done after an error");

        // A silent close is a failure, not an empty success.
        Catch empty = run("");
        check(empty.error != null, "empty stream fails");
        eq(Integer.valueOf(empty.dones), Integer.valueOf(0), "no done on empty stream");

        // A final event with no trailing blank line still counts.
        Catch tail = run("data: {\"choices\":[{\"delta\":{\"content\":\"z\"},"
                + "\"finish_reason\":\"stop\"}]}");
        eq(tail.text.toString(), "z", "unterminated final event read");
        eq(tail.finish, "stop", "finish reason from the final event");

        // [DONE] with no content at all: ended cleanly, nothing to show.
        Catch none = run("data: [DONE]\n\n");
        eq(none.error, null, "DONE alone is not an error");
        eq(Integer.valueOf(none.dones), Integer.valueOf(1), "DONE alone completes");

        // Cancelling stops delivery and reports neither done nor failure.
        Catch c = new Catch();
        Net.Call call = new Net.Call();
        call.cancel();
        Net.consume(new java.io.StringReader("data: {\"choices\":[{\"delta\":"
                + "{\"content\":\"nope\"}}]}\n\ndata: [DONE]\n\n"), c, call);
        eq(Integer.valueOf(c.dones), Integer.valueOf(0), "cancelled: no done");
        eq(c.error, null, "cancelled: no error");
        eq(c.text.toString(), "", "cancelled: nothing delivered");
    }
}
