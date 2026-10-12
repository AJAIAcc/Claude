package dev.aj.hermes;

import java.util.ArrayList;
import java.util.Collections;
import java.util.Comparator;
import java.util.List;
import java.util.Map;

/**
 * The conversation model, and its on-disk and on-the-wire forms.
 *
 * No Android imports, so it is tested on the desktop JVM. {@link #load} is
 * deliberately total: a store written by an older build, or truncated by a
 * crash, must come back as whatever conversations survive rather than
 * preventing the app from opening.
 */
final class Chat {

    static final String SYSTEM = "system";
    static final String USER = "user";
    static final String ASSISTANT = "assistant";

    /** Longest title kept for a list row. */
    private static final int TITLE = 44;

    static final class Message {
        final String role;
        String text;
        /** The reasoning trace, when the model produced one. Never sent back. */
        String reasoning;
        /** Set when a turn failed, so the transcript can show it as an error. */
        boolean failed;

        Message(String role, String text) {
            this(role, text, null);
        }

        Message(String role, String text, String reasoning) {
            this.role = role == null ? USER : role;
            this.text = text == null ? "" : text;
            this.reasoning = reasoning;
        }
    }

    static final class Conversation {
        final long id;
        final List<Message> messages = new ArrayList<Message>();
        long updated;
        /** Overrides the derived title when the user renames the chat. */
        String name;

        Conversation(long id) {
            this.id = id;
        }

        void add(Message m) {
            messages.add(m);
        }

        /** The last assistant message, or null. */
        Message lastAssistant() {
            for (int i = messages.size() - 1; i >= 0; i--) {
                if (messages.get(i).role.equals(ASSISTANT)) {
                    return messages.get(i);
                }
            }
            return null;
        }

        /** A label for the conversation list: the opening question, trimmed. */
        String title() {
            if (name != null && !name.trim().isEmpty()) {
                return name.trim();
            }
            for (int i = 0; i < messages.size(); i++) {
                Message m = messages.get(i);
                if (m.role.equals(USER) && !m.text.trim().isEmpty()) {
                    String t = m.text.trim().replace('\n', ' ').replace('\r', ' ');
                    if (t.length() > TITLE) {
                        // Prefer a word boundary, but only a late one. The budget
                        // is one short of TITLE to leave room for the ellipsis.
                        int room = TITLE - 1;
                        int cut = t.lastIndexOf(' ', room);
                        t = t.substring(0, cut > room - 12 ? cut : room).trim() + "…";
                    }
                    return t;
                }
            }
            return "New chat";
        }
    }

    private Chat() {
    }

    // ------------------------------------------------------------------ wire

    /**
     * The {@code messages} array for a request.
     *
     * Reasoning traces are left out: they are the model's scratch space, they
     * cost tokens to send, and Hermes is prompted to think afresh each turn.
     *
     * @param system  system prompt, or empty for none
     * @param maxTurns most recent messages to send, or 0 for all. Sending a
     *                 whole long chat each turn is what quietly runs up a bill.
     */
    static List<Object> wire(Conversation c, String system, int maxTurns) {
        List<Object> out = new ArrayList<Object>();
        if (system != null && !system.trim().isEmpty()) {
            out.add(one(SYSTEM, system.trim()));
        }
        int from = 0;
        if (maxTurns > 0 && c.messages.size() > maxTurns) {
            from = c.messages.size() - maxTurns;
        }
        for (int i = from; i < c.messages.size(); i++) {
            Message m = c.messages.get(i);
            if (m.failed || m.text.isEmpty()) {
                continue; // a failed turn is not part of the history
            }
            out.add(one(m.role, m.text));
        }
        return out;
    }

    private static Map<String, Object> one(String role, String content) {
        Map<String, Object> m = Json.map();
        m.put("role", role);
        m.put("content", content);
        return m;
    }

    // ----------------------------------------------------------------- store

    static String save(List<Conversation> all) {
        List<Object> rows = new ArrayList<Object>();
        for (int i = 0; i < all.size(); i++) {
            Conversation c = all.get(i);
            Map<String, Object> row = Json.map();
            row.put("id", Long.valueOf(c.id));
            row.put("updated", Long.valueOf(c.updated));
            if (c.name != null) {
                row.put("name", c.name);
            }
            List<Object> ms = new ArrayList<Object>();
            for (int k = 0; k < c.messages.size(); k++) {
                Message m = c.messages.get(k);
                if (m.failed) {
                    continue; // errors are not worth keeping across restarts
                }
                Map<String, Object> mm = Json.map();
                mm.put("role", m.role);
                mm.put("text", m.text);
                if (m.reasoning != null && !m.reasoning.isEmpty()) {
                    mm.put("reasoning", m.reasoning);
                }
                ms.add(mm);
            }
            row.put("messages", ms);
            rows.add(row);
        }
        Map<String, Object> doc = Json.map();
        doc.put("version", Long.valueOf(1));
        doc.put("conversations", rows);
        return Json.write(doc);
    }

    /** Never throws: an unreadable store yields the conversations it can. */
    static List<Conversation> load(String text) {
        List<Conversation> out = new ArrayList<Conversation>();
        if (text == null || text.trim().isEmpty()) {
            return out;
        }
        Object doc;
        try {
            doc = Json.parse(text);
        } catch (Json.Bad b) {
            return out;
        } catch (RuntimeException r) {
            return out;
        }
        List<Object> rows = Json.list(doc, "conversations");
        for (int i = 0; i < rows.size(); i++) {
            Object row = rows.get(i);
            Object idv = Json.dig(row, "id");
            long id = idv instanceof Number ? ((Number) idv).longValue() : (long) (i + 1);
            Conversation c = new Conversation(id);
            Object up = Json.dig(row, "updated");
            c.updated = up instanceof Number ? ((Number) up).longValue() : 0L;
            c.name = Json.str(row, "name");
            List<Object> ms = Json.list(row, "messages");
            for (int k = 0; k < ms.size(); k++) {
                Object m = ms.get(k);
                String role = Json.str(m, "role");
                String body = Json.str(m, "text");
                if (body == null) {
                    body = Json.str(m, "content"); // tolerate the wire spelling
                }
                if (role == null || body == null) {
                    continue;
                }
                c.add(new Message(role, body, Json.str(m, "reasoning")));
            }
            out.add(c);
        }
        return out;
    }

    /** Most recently updated first, for the conversation list. */
    static void sort(List<Conversation> all) {
        Collections.sort(all, new Comparator<Conversation>() {
            public int compare(Conversation a, Conversation b) {
                if (a.updated != b.updated) {
                    return a.updated > b.updated ? -1 : 1;
                }
                return a.id > b.id ? -1 : (a.id < b.id ? 1 : 0);
            }
        });
    }
}
