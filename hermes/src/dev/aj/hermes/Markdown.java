package dev.aj.hermes;

import java.util.ArrayList;
import java.util.List;

/**
 * Just enough Markdown to make a model's reply readable.
 *
 * The stub framework has no {@code Spannable}, so there is no way to style a
 * run of characters inside one {@code TextView}. Structure is therefore carried
 * by the <em>blocks</em> this returns — the renderer gives each one its own
 * view, so a code block really is a monospaced card and a heading really is
 * bold — while inline emphasis is reduced to its text by {@link #inline}.
 * Showing raw {@code **asterisks**} would be worse than dropping them.
 *
 * It is also run on partial text while a reply streams in, so an unterminated
 * code fence has to parse as a code block rather than disappearing.
 */
final class Markdown {

    static final int PARAGRAPH = 0;
    static final int HEADING = 1;
    static final int CODE = 2;
    static final int BULLET = 3;
    static final int QUOTE = 4;

    static final class Block {
        final int kind;
        final String text;
        /** Fence language, or null. Informational: nothing is highlighted. */
        final String lang;

        Block(int kind, String text, String lang) {
            this.kind = kind;
            this.text = text;
            this.lang = lang;
        }
    }

    private Markdown() {
    }

    static List<Block> parse(String src) {
        List<Block> out = new ArrayList<Block>();
        if (src == null) {
            return out;
        }
        String[] lines = src.split("\n", -1);
        List<String> para = new ArrayList<String>();
        int i = 0;
        while (i < lines.length) {
            String line = lines[i];
            String trimmed = line.trim();

            if (trimmed.startsWith("```") || trimmed.startsWith("~~~")) {
                flush(para, out);
                String fence = trimmed.substring(0, 3);
                String lang = trimmed.substring(3).trim();
                StringBuilder code = new StringBuilder();
                i++;
                boolean first = true;
                while (i < lines.length && !lines[i].trim().startsWith(fence)) {
                    if (!first) {
                        code.append('\n');
                    }
                    first = false;
                    code.append(lines[i]);
                    i++;
                }
                if (i < lines.length) {
                    i++; // the closing fence; absent while still streaming
                }
                out.add(new Block(CODE, trim(code.toString()), lang.isEmpty() ? null : lang));
                continue;
            }

            if (trimmed.isEmpty()) {
                flush(para, out);
                i++;
                continue;
            }

            if (trimmed.startsWith("#")) {
                int h = 0;
                while (h < trimmed.length() && trimmed.charAt(h) == '#' && h < 6) {
                    h++;
                }
                // "#tag" is not a heading; "# Title" is.
                if (h < trimmed.length() && trimmed.charAt(h) == ' ') {
                    flush(para, out);
                    out.add(new Block(HEADING, inline(trimmed.substring(h).trim()), null));
                    i++;
                    continue;
                }
            }

            if (trimmed.startsWith("> ") || trimmed.equals(">")) {
                flush(para, out);
                out.add(new Block(QUOTE, inline(trimmed.substring(1).trim()), null));
                i++;
                continue;
            }

            if (bullet(trimmed)) {
                flush(para, out);
                out.add(new Block(BULLET, inline(trimmed.substring(2).trim()), null));
                i++;
                continue;
            }

            if (numbered(trimmed)) {
                flush(para, out);
                // The number is kept: in a list of steps the order is the point.
                out.add(new Block(BULLET, inline(trimmed), null));
                i++;
                continue;
            }

            if (isRule(trimmed)) {
                flush(para, out);
                i++;
                continue;
            }

            para.add(trimmed);
            i++;
        }
        flush(para, out);
        return out;
    }

    private static boolean bullet(String s) {
        if (s.length() < 2) {
            return false;
        }
        char c = s.charAt(0);
        return (c == '-' || c == '*' || c == '+') && s.charAt(1) == ' ';
    }

    private static boolean numbered(String s) {
        int k = 0;
        while (k < s.length() && s.charAt(k) >= '0' && s.charAt(k) <= '9') {
            k++;
        }
        if (k == 0 || k >= s.length()) {
            return false;
        }
        char c = s.charAt(k);
        return (c == '.' || c == ')') && k + 1 < s.length() && s.charAt(k + 1) == ' ';
    }

    private static boolean isRule(String s) {
        if (s.length() < 3) {
            return false;
        }
        char c = s.charAt(0);
        if (c != '-' && c != '*' && c != '_') {
            return false;
        }
        for (int k = 0; k < s.length(); k++) {
            if (s.charAt(k) != c) {
                return false;
            }
        }
        return true;
    }

    private static void flush(List<String> para, List<Block> out) {
        if (para.isEmpty()) {
            return;
        }
        StringBuilder b = new StringBuilder();
        for (int k = 0; k < para.size(); k++) {
            if (k > 0) {
                b.append('\n');
            }
            b.append(para.get(k));
        }
        para.clear();
        String text = inline(b.toString());
        if (!text.isEmpty()) {
            out.add(new Block(PARAGRAPH, text, null));
        }
    }

    private static String trim(String s) {
        int a = 0;
        int b = s.length();
        while (a < b && (s.charAt(a) == '\n' || s.charAt(a) == '\r')) {
            a++;
        }
        while (b > a && (s.charAt(b - 1) == '\n' || s.charAt(b - 1) == '\r')) {
            b--;
        }
        return s.substring(a, b);
    }

    /**
     * Strips inline emphasis, leaving the words.
     *
     * A marker only counts when it actually pairs up and the span it opens is
     * not blank, so arithmetic like {@code 2 * 3 * 4} and identifiers like
     * {@code a_b_c} come through untouched. Single underscores are never
     * emphasis here for that reason — snake_case is far more likely than
     * {@code _emphasis_} in anything a coding model says.
     */
    static String inline(String s) {
        if (s == null || s.isEmpty()) {
            return "";
        }
        StringBuilder out = new StringBuilder();
        // Open markers, innermost last.
        List<String> open = new ArrayList<String>();
        int i = 0;
        while (i < s.length()) {
            char c = s.charAt(i);

            if (c == '`') {
                int j = s.indexOf('`', i + 1);
                if (j > i) {
                    out.append(s, i + 1, j); // verbatim: no markers inside code
                    i = j + 1;
                    continue;
                }
            }

            String pair = null;
            if (s.startsWith("**", i)) {
                pair = "**";
            } else if (s.startsWith("__", i)) {
                pair = "__";
            }
            if (pair != null) {
                if (!open.isEmpty() && open.get(open.size() - 1).equals(pair)
                        && i > 0 && !space(s.charAt(i - 1))) {
                    open.remove(open.size() - 1);
                    i += 2;
                    continue;
                }
                if (closes(s, i + 2, pair)) {
                    open.add(pair);
                    i += 2;
                    continue;
                }
            }

            if (c == '*') {
                if (!open.isEmpty() && open.get(open.size() - 1).equals("*")
                        && i > 0 && !space(s.charAt(i - 1))) {
                    open.remove(open.size() - 1);
                    i++;
                    continue;
                }
                if (i + 1 < s.length() && !space(s.charAt(i + 1)) && closes(s, i + 1, "*")) {
                    open.add("*");
                    i++;
                    continue;
                }
            }

            out.append(c);
            i++;
        }
        return out.toString();
    }

    /** Is there a usable closing {@code marker} at or after {@code from}? */
    private static boolean closes(String s, int from, String marker) {
        int at = s.indexOf(marker, from);
        while (at >= 0) {
            if (at > from && !space(s.charAt(at - 1))) {
                return true;
            }
            at = s.indexOf(marker, at + 1);
        }
        return false;
    }

    private static boolean space(char c) {
        return c == ' ' || c == '\t' || c == '\n' || c == '\r';
    }
}
