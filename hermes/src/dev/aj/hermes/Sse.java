package dev.aj.hermes;

import java.util.ArrayList;
import java.util.List;

/**
 * Server-sent events framing, as used by {@code /chat/completions} with
 * {@code "stream": true}.
 *
 * The transport is line-oriented but an <em>event</em> is not a line: fields
 * accumulate until a blank line delimits the event, and {@code data:} may
 * appear more than once, in which case the payloads join with newlines. Most
 * OpenAI-compatible servers emit one {@code data:} per event, but the spec
 * allows the general form and some gateways use it, so this decodes the
 * general form.
 *
 * Feed it {@link #line} for each line read; it returns a completed payload or
 * null. {@link #DONE} marks the terminator sentinel {@code data: [DONE]}.
 */
final class Sse {

    /** Returned by {@link #line} when the stream announces it is finished. */
    static final String DONE = "\u0000done";

    private final StringBuilder data = new StringBuilder();
    private boolean any;

    /**
     * @return the event's data payload once a blank line completes it,
     *         {@link #DONE} at the terminator, or null if more lines are needed.
     */
    String line(String raw) {
        if (raw == null) {
            return flush();
        }
        // Tolerate CR left over from CRLF framing.
        String s = raw;
        while (s.endsWith("\r")) {
            s = s.substring(0, s.length() - 1);
        }
        if (s.isEmpty()) {
            return flush();
        }
        if (s.charAt(0) == ':') {
            return null; // comment / keep-alive
        }
        int colon = s.indexOf(':');
        String field;
        String value;
        if (colon < 0) {
            field = s;
            value = "";
        } else {
            field = s.substring(0, colon);
            value = s.substring(colon + 1);
            // Exactly one leading space after the colon is part of the framing.
            if (value.startsWith(" ")) {
                value = value.substring(1);
            }
        }
        if (!field.equals("data")) {
            return null; // event:, id:, retry: are not used here
        }
        if (value.equals("[DONE]")) {
            return DONE;
        }
        if (any) {
            data.append('\n');
        }
        data.append(value);
        any = true;
        return null;
    }

    /** Completes the pending event, if any. Also call at end of stream. */
    String flush() {
        if (!any) {
            return null;
        }
        String out = data.toString();
        data.setLength(0);
        any = false;
        return out;
    }

    /**
     * Pulls the text a chunk adds. Handles both the streaming shape
     * ({@code choices[0].delta}) and the whole-response shape
     * ({@code choices[0].message}), so a non-streaming reply parses here too.
     *
     * @return {text, reasoning}; either may be null.
     */
    static String[] delta(Object chunk) {
        Object choice = Json.dig(chunk, "choices", Integer.valueOf(0));
        if (choice == null) {
            return new String[]{null, null};
        }
        String text = Json.str(choice, "delta", "content");
        if (text == null) {
            text = Json.str(choice, "message", "content");
        }
        // Providers differ on where separated reasoning lands.
        String think = Json.str(choice, "delta", "reasoning_content");
        if (think == null) {
            think = Json.str(choice, "delta", "reasoning");
        }
        if (think == null) {
            think = Json.str(choice, "message", "reasoning_content");
        }
        if (think == null) {
            think = Json.str(choice, "message", "reasoning");
        }
        return new String[]{text, think};
    }

    /** Why generation stopped, or null while it is still running. */
    static String finish(Object chunk) {
        return Json.str(Json.dig(chunk, "choices", Integer.valueOf(0)), "finish_reason");
    }

    /**
     * The human-readable message from an error body, whatever shape it takes:
     * {@code {"error":{"message":..}}}, {@code {"error":".."}},
     * {@code {"message":..}} or {@code {"detail":..}}.
     */
    static String error(Object body) {
        String m = Json.str(body, "error", "message");
        if (m == null) {
            m = Json.str(body, "error");
        }
        if (m == null) {
            m = Json.str(body, "message");
        }
        if (m == null) {
            m = Json.str(body, "detail");
        }
        return m;
    }

    /** Model ids from a {@code GET /v1/models} body, in the order given. */
    static List<String> models(Object body) {
        List<String> out = new ArrayList<String>();
        List<Object> rows = Json.list(body, "data");
        if (rows.isEmpty()) {
            rows = Json.list(body, "models");
        }
        if (rows.isEmpty() && body instanceof List) {
            rows = (List<Object>) body;
        }
        for (int k = 0; k < rows.size(); k++) {
            Object row = rows.get(k);
            String id = Json.str(row, "id");
            if (id == null) {
                id = Json.str(row, "name");
            }
            if (id == null && row instanceof String) {
                id = (String) row;
            }
            if (id != null && !id.isEmpty() && !out.contains(id)) {
                out.add(id);
            }
        }
        return out;
    }
}
