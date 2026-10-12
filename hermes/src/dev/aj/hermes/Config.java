package dev.aj.hermes;

import android.content.Context;
import android.content.SharedPreferences;

/**
 * Settings, kept in the app's private {@code SharedPreferences}.
 *
 * The API key lives here in the clear. On Android that file is inside the
 * app's private data directory, readable only by this app's uid, which is the
 * same protection the platform's own accounts get — but it is not encrypted,
 * so on a rooted or unlocked-bootloader phone it is readable. That trade is
 * documented in the README rather than hidden behind a passphrase prompt the
 * app would have to ask for on every launch.
 */
final class Config {

    private static final String FILE = "hermes";

    private static final String BASE = "base_url";
    private static final String KEY = "api_key";
    private static final String MODEL = "model";
    private static final String SYSTEM = "system_prompt";
    private static final String TEMP = "temperature";
    private static final String MAXTOK = "max_tokens";
    private static final String STREAM = "stream";
    private static final String SHOW_REASONING = "show_reasoning";
    private static final String HISTORY = "history";

    private final SharedPreferences p;

    Config(Context c) {
        p = c.getSharedPreferences(FILE, Context.MODE_PRIVATE);
    }

    // ------------------------------------------------------------------ read

    String baseUrl() {
        String s = p.getString(BASE, Defaults.BASE_URL);
        return s == null || s.trim().isEmpty() ? Defaults.BASE_URL : s.trim();
    }

    String apiKey() {
        String s = p.getString(KEY, "");
        return s == null ? "" : s.trim();
    }

    String model() {
        String s = p.getString(MODEL, Defaults.MODEL);
        return s == null || s.trim().isEmpty() ? Defaults.MODEL : s.trim();
    }

    String systemPrompt() {
        String s = p.getString(SYSTEM, Defaults.SYSTEM_PROMPT);
        return s == null ? "" : s;
    }

    double temperature() {
        float t = p.getFloat(TEMP, (float) Defaults.TEMPERATURE);
        if (t < 0.0f) {
            return 0.0;
        }
        if (t > 2.0f) {
            return 2.0;
        }
        // Rounded on the way out: 0.7 stored as a float widens to
        // 0.69999998..., which would otherwise be shown as "0.69".
        return Math.round((double) t * 100.0) / 100.0;
    }

    int maxTokens() {
        int v = p.getInt(MAXTOK, Defaults.MAX_TOKENS);
        return v < 0 ? 0 : v;
    }

    boolean stream() {
        return p.getBoolean(STREAM, true);
    }

    boolean showReasoning() {
        return p.getBoolean(SHOW_REASONING, true);
    }

    int history() {
        int v = p.getInt(HISTORY, Defaults.HISTORY);
        return v < 0 ? 0 : v;
    }

    /** Is there enough to send a request? */
    boolean ready() {
        return !apiKey().isEmpty();
    }

    /** The settings {@link Net} needs, snapshotted for a worker thread. */
    Net.Params params() {
        Net.Params q = new Net.Params();
        q.baseUrl = baseUrl();
        q.apiKey = apiKey();
        q.model = model();
        q.temperature = temperature();
        q.maxTokens = maxTokens();
        q.stream = stream();
        return q;
    }

    // ----------------------------------------------------------------- write

    void setBaseUrl(String v) {
        put(BASE, v == null ? "" : v.trim());
    }

    void setApiKey(String v) {
        put(KEY, v == null ? "" : v.trim());
    }

    void setModel(String v) {
        put(MODEL, v == null ? "" : v.trim());
    }

    void setSystemPrompt(String v) {
        put(SYSTEM, v == null ? "" : v);
    }

    void setTemperature(double v) {
        p.edit().putFloat(TEMP, (float) v).apply();
    }

    void setMaxTokens(int v) {
        p.edit().putInt(MAXTOK, v < 0 ? 0 : v).apply();
    }

    void setStream(boolean v) {
        p.edit().putBoolean(STREAM, v).apply();
    }

    void setShowReasoning(boolean v) {
        p.edit().putBoolean(SHOW_REASONING, v).apply();
    }

    void setHistory(int v) {
        p.edit().putInt(HISTORY, v < 0 ? 0 : v).apply();
    }

    private void put(String k, String v) {
        p.edit().putString(k, v).apply();
    }
}
