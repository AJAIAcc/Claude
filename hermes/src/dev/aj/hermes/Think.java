package dev.aj.hermes;

/**
 * Separates a Hermes reasoning trace from its answer.
 *
 * Hermes 4 is a hybrid reasoner: in thinking mode the trace arrives inline in
 * {@code content}, wrapped in {@code <think>…</think>}, rather than on a
 * separate field. Shown raw it reads as the model talking to itself before
 * answering, so it is split out and collapsed in the transcript.
 *
 * The hard part is that this is a token stream: {@code <think>} can arrive as
 * {@code "<thi"} then {@code "nk>"}, and a chunk ending in {@code "<"} may or
 * may not be the start of a tag. So any suffix that could still grow into a
 * tag is held back rather than emitted as text — which is why
 * {@link #finish} exists, to release a held-back suffix that turned out to be
 * ordinary text after all.
 */
final class Think {

    /** Where split text goes. Both halves arrive incrementally. */
    interface Sink {
        void answer(String text);

        void reasoning(String text);
    }

    private static final String OPEN = "<think>";
    private static final String CLOSE = "</think>";

    private final Sink sink;
    private final StringBuilder held = new StringBuilder();
    private boolean inside;
    private boolean sawAny;

    Think(Sink sink) {
        this.sink = sink;
    }

    /** True once an opening tag has been seen, i.e. this reply has a trace. */
    boolean sawReasoning() {
        return sawAny;
    }

    /** True while inside a trace, so the UI can label what is streaming. */
    boolean thinking() {
        return inside;
    }

    void feed(String chunk) {
        if (chunk == null || chunk.isEmpty()) {
            return;
        }
        held.append(chunk);
        pump(false);
    }

    /** End of stream: release whatever is held, tag-looking or not. */
    void finish() {
        pump(true);
        if (held.length() > 0) {
            emit(held.toString());
            held.setLength(0);
        }
    }

    private void pump(boolean draining) {
        while (true) {
            String s = held.toString();
            String tag = inside ? CLOSE : OPEN;
            int at = s.indexOf(tag);
            if (at >= 0) {
                if (at > 0) {
                    emit(s.substring(0, at));
                }
                held.delete(0, at + tag.length());
                if (!inside) {
                    sawAny = true;
                }
                inside = !inside;
                continue;
            }
            if (draining) {
                return;
            }
            // No tag. Emit everything except a suffix that could still become one.
            int hold = partial(s, tag);
            int safe = s.length() - hold;
            if (safe > 0) {
                emit(s.substring(0, safe));
                held.delete(0, safe);
            }
            return;
        }
    }

    private void emit(String text) {
        if (text.isEmpty()) {
            return;
        }
        if (inside) {
            sink.reasoning(text);
        } else {
            sink.answer(text);
        }
    }

    /**
     * How many trailing characters of {@code s} form a proper prefix of
     * {@code tag} — the amount that must be held back in case the rest of the
     * tag is in the next chunk.
     */
    private static int partial(String s, String tag) {
        int max = Math.min(s.length(), tag.length() - 1);
        for (int n = max; n > 0; n--) {
            if (s.regionMatches(s.length() - n, tag, 0, n)) {
                return n;
            }
        }
        return 0;
    }
}
