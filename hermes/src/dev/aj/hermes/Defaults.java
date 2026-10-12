package dev.aj.hermes;

/**
 * Where the app points when nothing has been configured.
 *
 * The defaults are Nous Research's hosted Hermes endpoint, which speaks the
 * OpenAI chat-completions dialect. They are only defaults: base URL, model and
 * key are all editable in Settings, so the same build works against any
 * compatible endpoint (a gateway, a proxy, or another provider's Hermes
 * deployment) without being rebuilt. That matters because a provider can move
 * a path or rename a model, and an app that hardcodes them becomes scrap.
 */
final class Defaults {

    static final String VERSION = "1.0";

    /** Nous's inference API. The {@code /v1} is part of it. */
    static final String BASE_URL = "https://inference-api.nousresearch.com/v1";

    static final String MODEL = "Hermes-4-70B";

    /**
     * Offered in the model picker before the endpoint has been asked for its
     * own list, which is the authoritative one — these are a starting point,
     * not a claim about what a given key can reach.
     */
    static final String[] MODELS = {
            "Hermes-4-405B",
            "Hermes-4-70B",
            "Hermes-3-Llama-3.1-70B",
            "Hermes-3-Llama-3.1-8B",
            "DeepHermes-3-Llama-3-8B-Preview",
    };

    /**
     * Empty by default. Hermes is steerable and neutral out of the box; an
     * invented persona would be us putting words in the model's mouth.
     */
    static final String SYSTEM_PROMPT = "";

    /** A thinking-mode prompt, offered as a one-tap preset in Settings. */
    static final String REASONING_PROMPT =
            "You are a deep thinking AI. You may use extremely long chains of thought "
            + "to deeply consider the problem and deliberate with yourself via systematic "
            + "reasoning processes to help come to a correct solution prior to answering. "
            + "Enclose your thoughts inside <think> </think> tags, then provide your answer.";

    static final double TEMPERATURE = 0.7;

    /** 0 means "don't send max_tokens", i.e. let the server decide. */
    static final int MAX_TOKENS = 0;

    /**
     * How many past messages go with each turn. Capped by default: the whole
     * history is re-sent on every turn, so an unbounded chat quietly costs
     * more each time.
     */
    static final int HISTORY = 24;

    private Defaults() {
    }
}
