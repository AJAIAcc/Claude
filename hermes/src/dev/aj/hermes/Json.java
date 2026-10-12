package dev.aj.hermes;

import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

/**
 * A small JSON reader and writer.
 *
 * droidforge compiles against the JDK's {@code java.*} classes plus a stub
 * android.jar, and {@code org.json} is in neither, so the wire format is done
 * by hand here. It is also the only part of the app that touches untrusted
 * input, so it is deliberately total: every parse failure is a {@link Bad},
 * never a {@code RuntimeException} escaping into the UI thread.
 *
 * Values map to: {@link Map} (insertion-ordered), {@link List}, {@link String},
 * {@link Long} or {@link Double}, {@link Boolean}, and null.
 */
final class Json {

    /** Malformed input. Carries the offset so a bad reply can be reported usefully. */
    static final class Bad extends Exception {
        Bad(String message) {
            super(message);
        }
    }

    /** Nesting cap: a hostile or broken reply must not recurse us into a stack overflow. */
    private static final int MAX_DEPTH = 96;

    private final String s;
    private int i;

    private Json(String s) {
        this.s = s;
    }

    // ------------------------------------------------------------------ read

    static Object parse(String text) throws Bad {
        if (text == null) {
            throw new Bad("no content");
        }
        Json p = new Json(text);
        p.ws();
        Object v = p.value(0);
        p.ws();
        if (p.i < p.s.length()) {
            throw new Bad("trailing text at " + p.i);
        }
        return v;
    }

    private Object value(int depth) throws Bad {
        if (depth > MAX_DEPTH) {
            throw new Bad("nested too deeply");
        }
        if (i >= s.length()) {
            throw new Bad("unexpected end of input");
        }
        char c = s.charAt(i);
        if (c == '{') {
            return object(depth);
        }
        if (c == '[') {
            return array(depth);
        }
        if (c == '"') {
            return string();
        }
        if (c == 't') {
            lit("true");
            return Boolean.TRUE;
        }
        if (c == 'f') {
            lit("false");
            return Boolean.FALSE;
        }
        if (c == 'n') {
            lit("null");
            return null;
        }
        return number();
    }

    private Map<String, Object> object(int depth) throws Bad {
        i++; // {
        Map<String, Object> m = new LinkedHashMap<String, Object>();
        ws();
        if (at('}')) {
            i++;
            return m;
        }
        while (true) {
            ws();
            if (i >= s.length() || s.charAt(i) != '"') {
                throw new Bad("expected a key at " + i);
            }
            String k = string();
            ws();
            expect(':');
            ws();
            m.put(k, value(depth + 1));
            ws();
            if (at(',')) {
                i++;
                continue;
            }
            expect('}');
            return m;
        }
    }

    private List<Object> array(int depth) throws Bad {
        i++; // [
        List<Object> l = new ArrayList<Object>();
        ws();
        if (at(']')) {
            i++;
            return l;
        }
        while (true) {
            ws();
            l.add(value(depth + 1));
            ws();
            if (at(',')) {
                i++;
                continue;
            }
            expect(']');
            return l;
        }
    }

    private String string() throws Bad {
        i++; // opening quote
        StringBuilder b = new StringBuilder();
        while (true) {
            if (i >= s.length()) {
                throw new Bad("unterminated string");
            }
            char c = s.charAt(i++);
            if (c == '"') {
                return b.toString();
            }
            if (c != '\\') {
                b.append(c);
                continue;
            }
            if (i >= s.length()) {
                throw new Bad("unterminated escape");
            }
            char e = s.charAt(i++);
            if (e == '"' || e == '\\' || e == '/') {
                b.append(e);
            } else if (e == 'n') {
                b.append('\n');
            } else if (e == 't') {
                b.append('\t');
            } else if (e == 'r') {
                b.append('\r');
            } else if (e == 'b') {
                b.append('\b');
            } else if (e == 'f') {
                b.append('\f');
            } else if (e == 'u') {
                if (i + 4 > s.length()) {
                    throw new Bad("short \\u escape");
                }
                int v = 0;
                for (int k = 0; k < 4; k++) {
                    int d = hex(s.charAt(i + k));
                    if (d < 0) {
                        throw new Bad("bad \\u escape at " + i);
                    }
                    v = (v << 4) | d;
                }
                i += 4;
                // Appending each unit is right: Java strings are UTF-16, so a
                // surrogate pair arrives as two escapes and reassembles itself.
                b.append((char) v);
            } else {
                throw new Bad("unknown escape \\" + e);
            }
        }
    }

    private Object number() throws Bad {
        int start = i;
        if (at('-') || at('+')) {
            i++;
        }
        boolean real = false;
        while (i < s.length()) {
            char c = s.charAt(i);
            if (c >= '0' && c <= '9') {
                i++;
            } else if (c == '.' || c == 'e' || c == 'E' || c == '+' || c == '-') {
                real = real || c == '.' || c == 'e' || c == 'E';
                i++;
            } else {
                break;
            }
        }
        String t = s.substring(start, i);
        if (t.isEmpty() || t.equals("-") || t.equals("+")) {
            throw new Bad("expected a value at " + start);
        }
        try {
            if (!real) {
                return Long.valueOf(Long.parseLong(t));
            }
        } catch (NumberFormatException nfe) {
            // too wide for a long; fall through to double
        }
        try {
            return Double.valueOf(Double.parseDouble(t));
        } catch (NumberFormatException nfe) {
            throw new Bad("bad number " + t);
        }
    }

    private static int hex(char c) {
        if (c >= '0' && c <= '9') {
            return c - '0';
        }
        if (c >= 'a' && c <= 'f') {
            return c - 'a' + 10;
        }
        if (c >= 'A' && c <= 'F') {
            return c - 'A' + 10;
        }
        return -1;
    }

    private boolean at(char c) {
        return i < s.length() && s.charAt(i) == c;
    }

    private void expect(char c) throws Bad {
        if (!at(c)) {
            throw new Bad("expected '" + c + "' at " + i);
        }
        i++;
    }

    private void lit(String word) throws Bad {
        if (!s.startsWith(word, i)) {
            throw new Bad("expected " + word + " at " + i);
        }
        i += word.length();
    }

    private void ws() {
        while (i < s.length()) {
            char c = s.charAt(i);
            if (c == ' ' || c == '\t' || c == '\n' || c == '\r') {
                i++;
            } else {
                return;
            }
        }
    }

    // --------------------------------------------------------------- lookups

    /**
     * Walks {@code path} (String keys, Integer indices) and returns what is
     * there, or null if any step is missing or the wrong shape. Reply shapes
     * vary between providers, so every read goes through this rather than
     * trusting a cast.
     */
    static Object dig(Object node, Object... path) {
        Object cur = node;
        for (int k = 0; k < path.length; k++) {
            if (cur == null) {
                return null;
            }
            Object step = path[k];
            if (step instanceof String) {
                if (!(cur instanceof Map)) {
                    return null;
                }
                cur = ((Map) cur).get(step);
            } else if (step instanceof Integer) {
                if (!(cur instanceof List)) {
                    return null;
                }
                List l = (List) cur;
                int idx = ((Integer) step).intValue();
                if (idx < 0 || idx >= l.size()) {
                    return null;
                }
                cur = l.get(idx);
            } else {
                return null;
            }
        }
        return cur;
    }

    /** The string at {@code path}, or null. Non-strings do not count. */
    static String str(Object node, Object... path) {
        Object v = dig(node, path);
        return v instanceof String ? (String) v : null;
    }

    /** The list at {@code path}, or an empty list. */
    static List<Object> list(Object node, Object... path) {
        Object v = dig(node, path);
        return v instanceof List ? (List<Object>) v : new ArrayList<Object>();
    }

    // -------------------------------------------------------------- write

    static String write(Object v) {
        StringBuilder b = new StringBuilder();
        put(b, v);
        return b.toString();
    }

    private static void put(StringBuilder b, Object v) {
        if (v == null) {
            b.append("null");
        } else if (v instanceof String) {
            quote(b, (String) v);
        } else if (v instanceof Boolean) {
            b.append(((Boolean) v).booleanValue() ? "true" : "false");
        } else if (v instanceof Double || v instanceof Float) {
            double d = ((Number) v).doubleValue();
            // JSON has no infinity or NaN; emit something parseable instead.
            if (Double.isNaN(d) || Double.isInfinite(d)) {
                b.append('0');
            } else if (d == Math.floor(d) && Math.abs(d) < 1e15) {
                b.append(Long.toString((long) d));
            } else {
                b.append(Double.toString(d));
            }
        } else if (v instanceof Number) {
            b.append(v.toString());
        } else if (v instanceof Map) {
            b.append('{');
            boolean first = true;
            Map m = (Map) v;
            for (Object e : m.entrySet()) {
                Map.Entry en = (Map.Entry) e;
                if (!first) {
                    b.append(',');
                }
                first = false;
                quote(b, String.valueOf(en.getKey()));
                b.append(':');
                put(b, en.getValue());
            }
            b.append('}');
        } else if (v instanceof List) {
            b.append('[');
            List l = (List) v;
            for (int k = 0; k < l.size(); k++) {
                if (k > 0) {
                    b.append(',');
                }
                put(b, l.get(k));
            }
            b.append(']');
        } else {
            quote(b, v.toString());
        }
    }

    private static void quote(StringBuilder b, String s) {
        b.append('"');
        for (int k = 0; k < s.length(); k++) {
            char c = s.charAt(k);
            if (c == '"') {
                b.append("\\\"");
            } else if (c == '\\') {
                b.append("\\\\");
            } else if (c == '\n') {
                b.append("\\n");
            } else if (c == '\r') {
                b.append("\\r");
            } else if (c == '\t') {
                b.append("\\t");
            } else if (c == '\b') {
                b.append("\\b");
            } else if (c == '\f') {
                b.append("\\f");
            } else if (c < 0x20 || c == 0x2028 || c == 0x2029) {
                b.append("\\u");
                String h = Integer.toHexString(c);
                for (int p = h.length(); p < 4; p++) {
                    b.append('0');
                }
                b.append(h);
            } else {
                b.append(c);
            }
        }
        b.append('"');
    }

    /** Convenience for building request bodies. */
    static Map<String, Object> map() {
        return new LinkedHashMap<String, Object>();
    }
}
