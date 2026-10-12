package dev.aj.hermes;

import android.app.Activity;
import android.os.Bundle;
import android.os.SystemClock;
import android.text.InputType;
import android.view.Gravity;
import android.view.View;
import android.view.ViewGroup;
import android.widget.EditText;
import android.widget.HorizontalScrollView;
import android.widget.LinearLayout;
import android.widget.ScrollView;
import android.widget.TextView;
import android.widget.Toast;

import java.io.IOException;
import java.util.ArrayList;
import java.util.List;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

/**
 * One activity holding a small stack of screens: the chat, the chat list and
 * settings. Each screen rebuilds itself from the store when shown, so nothing
 * in the interface can hold a stale copy of a conversation.
 *
 * Threading: requests run on a single worker thread and report back through
 * {@link Net.Sink} on that thread. Deltas are appended to a buffer under
 * {@link #lock} and the UI is refreshed on a timer, because a reply can arrive
 * faster than the view system can lay out — a {@code setText} per token would
 * make the phone stutter and drop frames.
 */
public class MainActivity extends Activity {

    /** How often the transcript is redrawn while a reply streams in. */
    private static final long FLUSH_MS = 60;

    /** A page of the interface. */
    abstract static class Screen {
        abstract String title();

        abstract void build(LinearLayout into);

        /** Optional header action label. */
        String action() {
            return null;
        }

        void onAction() {
        }

        /** Does this screen show the message composer? */
        boolean composer() {
            return false;
        }

        /** Second line in the header, if any. */
        String subtitle() {
            return null;
        }

        void onSubtitle() {
        }
    }

    private Config cfg;
    private Store store;
    private List<Chat.Conversation> chats = new ArrayList<Chat.Conversation>();
    private Chat.Conversation current;

    private final List<Screen> stack = new ArrayList<Screen>();

    // Shell views.
    private LinearLayout shell;
    private LinearLayout content;
    private ScrollView scroller;
    private TextView titleView;
    private TextView subtitleView;
    private TextView backView;
    private TextView actionView;
    private LinearLayout composerBar;
    private EditText input;
    private TextView sendView;

    // Streaming state. Buffers are shared with the worker thread.
    private final Object lock = new Object();
    private final StringBuilder liveAnswer = new StringBuilder();
    private final StringBuilder liveThink = new StringBuilder();
    private volatile boolean flushPending;
    /** The in-flight call, or null when idle. Touched on the UI thread only. */
    private Net.Call call;
    private TextView liveText;
    private TextView liveThinkText;
    private LinearLayout liveThinkBox;
    private TextView liveStatus;
    private boolean traceOpen;

    private final ExecutorService worker = Executors.newSingleThreadExecutor();

    // ------------------------------------------------------------- lifecycle

    protected void onCreate(Bundle saved) {
        super.onCreate(saved);
        cfg = new Config(this);
        store = new Store(this);
        chats = store.load();
        if (chats.isEmpty()) {
            chats.add(new Chat.Conversation(now()));
        }
        current = chats.get(0);
        traceOpen = cfg.showReasoning();
        buildShell();
        push(new ChatScreen());
    }

    protected void onDestroy() {
        if (call != null) {
            call.cancel();
            call = null;
        }
        worker.shutdownNow();
        super.onDestroy();
    }

    public void onBackPressed() {
        if (stack.size() > 1) {
            stack.remove(stack.size() - 1);
            show();
            return;
        }
        super.onBackPressed();
    }

    private static long now() {
        return System.currentTimeMillis();
    }

    // ------------------------------------------------------------------ shell

    private void buildShell() {
        try {
            getWindow().setStatusBarColor(Ui.ACCENT_DEEP);
        } catch (Throwable t) {
            // not fatal if the platform refuses
        }

        shell = Ui.col(this);
        shell.setBackgroundColor(Ui.BG);

        LinearLayout header = Ui.row(this);
        header.setBackgroundColor(Ui.CARD);
        header.setPadding(Ui.dp(this, 14), Ui.dp(this, 12), Ui.dp(this, 14), Ui.dp(this, 12));

        backView = Ui.text(this, "‹", 26.0f, Ui.ACCENT, false);
        backView.setClickable(true);
        backView.setPadding(0, 0, Ui.dp(this, 12), 0);
        backView.setOnClickListener(new View.OnClickListener() {
            public void onClick(View v) {
                onBackPressed();
            }
        });
        header.addView(backView, Ui.wrap());

        LinearLayout titles = Ui.col(this);
        titleView = Ui.text(this, "Hermes", 18.0f, Ui.TEXT, true);
        titles.addView(titleView, Ui.wide());
        subtitleView = Ui.text(this, "", 12.0f, Ui.ACCENT, false);
        subtitleView.setClickable(true);
        titles.addView(subtitleView, Ui.wide());
        header.addView(titles, Ui.grow());

        actionView = Ui.text(this, "", 15.0f, Ui.ACCENT, true);
        actionView.setClickable(true);
        actionView.setPadding(Ui.dp(this, 10), 0, 0, 0);
        header.addView(actionView, Ui.wrap());
        shell.addView(header, Ui.wide());
        shell.addView(Ui.divider(this), Ui.dividerParams(this));

        scroller = new ScrollView(this);
        scroller.setFillViewport(true);
        content = Ui.col(this);
        content.setPadding(Ui.dp(this, 12), Ui.dp(this, 12), Ui.dp(this, 12), Ui.dp(this, 16));
        scroller.addView(content, new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT));
        shell.addView(scroller, Ui.fill());

        shell.addView(buildComposer(), Ui.wide());
        setContentView(shell);
    }

    private LinearLayout buildComposer() {
        composerBar = Ui.col(this);
        composerBar.setBackgroundColor(Ui.CARD);
        LinearLayout line = Ui.row(this);
        line.setPadding(Ui.dp(this, 10), Ui.dp(this, 8), Ui.dp(this, 10), Ui.dp(this, 10));

        input = new EditText(this);
        input.setHint("Message Hermes…");
        input.setHintTextColor(Ui.FAINT);
        input.setTextColor(Ui.TEXT);
        input.setTextSize(15.0f);
        input.setInputType(InputType.TYPE_CLASS_TEXT
                | InputType.TYPE_TEXT_FLAG_MULTI_LINE
                | InputType.TYPE_TEXT_FLAG_CAP_SENTENCES);
        input.setMaxLines(5);
        input.setBackground(Ui.outline(this, Ui.BG, Ui.LINE, 12));
        input.setPadding(Ui.dp(this, 12), Ui.dp(this, 10), Ui.dp(this, 12), Ui.dp(this, 10));
        line.addView(input, Ui.grow());

        sendView = Ui.button(this, "Send", Ui.ACCENT, 0xFFFFFFFF);
        sendView.setOnClickListener(new View.OnClickListener() {
            public void onClick(View v) {
                if (call != null) {
                    stop();
                } else {
                    send();
                }
            }
        });
        line.addView(sendView, Ui.margins(Ui.wrap(), this, 8, 0, 0, 0));

        composerBar.addView(Ui.divider(this), new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, Math.max(1, Ui.dp(this, 0.6f))));
        composerBar.addView(line, Ui.wide());
        return composerBar;
    }

    private void push(Screen s) {
        stack.add(s);
        show();
    }

    /** Rebuilds the visible screen from scratch. */
    private void show() {
        Screen s = stack.get(stack.size() - 1);
        titleView.setText(s.title());

        String sub = s.subtitle();
        if (sub == null || sub.isEmpty()) {
            subtitleView.setVisibility(View.GONE);
        } else {
            subtitleView.setVisibility(View.VISIBLE);
            subtitleView.setText(sub);
            final Screen target = s;
            subtitleView.setOnClickListener(new View.OnClickListener() {
                public void onClick(View v) {
                    target.onSubtitle();
                }
            });
        }

        backView.setVisibility(stack.size() > 1 ? View.VISIBLE : View.GONE);

        String a = s.action();
        if (a == null) {
            actionView.setVisibility(View.GONE);
        } else {
            actionView.setVisibility(View.VISIBLE);
            actionView.setText(a);
            final Screen target = s;
            actionView.setOnClickListener(new View.OnClickListener() {
                public void onClick(View v) {
                    target.onAction();
                }
            });
        }

        composerBar.setVisibility(s.composer() ? View.VISIBLE : View.GONE);
        liveText = null;
        liveThinkText = null;
        liveThinkBox = null;
        liveStatus = null;
        content.removeAllViews();
        s.build(content);
    }

    private void toast(String msg) {
        Toast.makeText(this, msg, Toast.LENGTH_LONG).show();
    }

    private void save() {
        if (!store.save(chats)) {
            toast("Couldn't save to storage — the device may be full.");
        }
    }

    // ------------------------------------------------------------ chat screen

    private final class ChatScreen extends Screen {
        String title() {
            return "Hermes";
        }

        String subtitle() {
            return cfg.model();
        }

        void onSubtitle() {
            pickModel();
        }

        String action() {
            return "Chats";
        }

        void onAction() {
            push(new ChatsScreen());
        }

        boolean composer() {
            return true;
        }

        void build(LinearLayout into) {
            if (!cfg.ready()) {
                into.addView(intro(), Ui.margins(Ui.wide(), MainActivity.this, 0, 0, 0, 12));
            }
            if (current.messages.isEmpty() && call == null) {
                into.addView(empty(), Ui.margins(Ui.wide(), MainActivity.this, 0, 8, 0, 0));
            }
            for (int i = 0; i < current.messages.size(); i++) {
                addBubble(into, current.messages.get(i), i);
            }
            if (call != null) {
                addLiveBubble(into);
            }
            scrollToBottom();
        }

        private View intro() {
            LinearLayout c = Ui.card(MainActivity.this, Ui.ACCENT_SOFT);
            c.addView(Ui.text(MainActivity.this, "Add your API key to begin",
                    15.0f, Ui.ACCENT_DEEP, true), Ui.wide());
            TextView body = Ui.text(MainActivity.this,
                    "This app talks to Hermes over an OpenAI-compatible API. "
                    + "Paste a key from your provider, and change the endpoint or model "
                    + "at any time in Settings.", 13.0f, Ui.ACCENT_DEEP, false);
            c.addView(body, Ui.margins(Ui.wide(), MainActivity.this, 0, 6, 0, 10));
            TextView go = Ui.button(MainActivity.this, "Open settings", Ui.ACCENT, 0xFFFFFFFF);
            go.setOnClickListener(new View.OnClickListener() {
                public void onClick(View v) {
                    push(new SettingsScreen());
                }
            });
            c.addView(go, Ui.wrap());
            return c;
        }

        private View empty() {
            LinearLayout c = Ui.col(MainActivity.this);
            c.setGravity(Gravity.CENTER_HORIZONTAL);
            c.setPadding(0, Ui.dp(MainActivity.this, 28), 0, 0);
            TextView t = Ui.text(MainActivity.this, "Ask Hermes anything.", 15.0f, Ui.MUTED, false);
            t.setGravity(Gravity.CENTER);
            c.addView(t, Ui.wide());
            TextView s = Ui.text(MainActivity.this, cfg.model(), 12.0f, Ui.FAINT, false);
            s.setGravity(Gravity.CENTER);
            c.addView(s, Ui.margins(Ui.wide(), MainActivity.this, 0, 4, 0, 0));
            return c;
        }
    }

    /** One stored message. */
    private void addBubble(LinearLayout into, Chat.Message m, final int index) {
        if (m.role.equals(Chat.USER)) {
            LinearLayout c = Ui.card(this, Ui.ACCENT_SOFT);
            TextView t = Ui.text(this, m.text, 15.0f, Ui.ACCENT_DEEP, false);
            t.setTextIsSelectable(true);
            c.addView(t, Ui.wide());
            // Indented on the left so the two sides of the conversation differ
            // in shape as well as colour.
            into.addView(c, Ui.margins(Ui.wide(), this, 36, 4, 0, 8));
            return;
        }
        if (m.failed) {
            LinearLayout c = Ui.card(this, Ui.ERR_BG);
            c.addView(Ui.text(this, m.text, 13.5f, Ui.ERR, false), Ui.wide());
            TextView retry = Ui.text(this, "Try again", 14.0f, Ui.ACCENT, true);
            retry.setClickable(true);
            retry.setPadding(0, Ui.dp(this, 8), 0, 0);
            retry.setOnClickListener(new View.OnClickListener() {
                public void onClick(View v) {
                    retryFrom(index);
                }
            });
            c.addView(retry, Ui.wrap());
            into.addView(c, Ui.margins(Ui.wide(), this, 0, 4, 36, 8));
            return;
        }

        LinearLayout c = Ui.card(this, Ui.CARD);
        if (m.reasoning != null && !m.reasoning.isEmpty()) {
            c.addView(traceBox(m.reasoning), Ui.margins(Ui.wide(), this, 0, 0, 0, 8));
        }
        renderMarkdown(c, m.text);
        into.addView(c, Ui.margins(Ui.wide(), this, 0, 4, 36, 8));
    }

    /** A collapsible reasoning trace. */
    private View traceBox(final String trace) {
        final LinearLayout box = Ui.col(this);
        box.setBackground(Ui.panel(this, Ui.THINK_BG, 10));
        box.setPadding(Ui.dp(this, 10), Ui.dp(this, 8), Ui.dp(this, 10), Ui.dp(this, 8));

        final TextView head = Ui.text(this,
                (traceOpen ? "▾  " : "▸  ") + "Reasoning", 12.5f, Ui.THINK_TEXT, true);
        head.setClickable(true);
        box.addView(head, Ui.wide());

        final TextView body = Ui.text(this, trace.trim(), 12.5f, Ui.THINK_TEXT, false);
        body.setTextIsSelectable(true);
        body.setVisibility(traceOpen ? View.VISIBLE : View.GONE);
        box.addView(body, Ui.margins(Ui.wide(), this, 0, 6, 0, 0));

        head.setOnClickListener(new View.OnClickListener() {
            public void onClick(View v) {
                boolean open = body.getVisibility() != View.VISIBLE;
                body.setVisibility(open ? View.VISIBLE : View.GONE);
                head.setText((open ? "▾  " : "▸  ") + "Reasoning");
                traceOpen = open;
            }
        });
        return box;
    }

    /**
     * The bubble a reply streams into. Plain text while it arrives — the
     * Markdown pass runs once at the end, when the text has stopped moving.
     */
    private void addLiveBubble(LinearLayout into) {
        LinearLayout c = Ui.card(this, Ui.CARD);

        liveThinkBox = Ui.col(this);
        liveThinkBox.setBackground(Ui.panel(this, Ui.THINK_BG, 10));
        liveThinkBox.setPadding(Ui.dp(this, 10), Ui.dp(this, 8), Ui.dp(this, 10), Ui.dp(this, 8));
        liveThinkBox.addView(Ui.text(this, "Thinking…", 12.5f, Ui.THINK_TEXT, true), Ui.wide());
        liveThinkText = Ui.text(this, "", 12.5f, Ui.THINK_TEXT, false);
        liveThinkBox.addView(liveThinkText, Ui.margins(Ui.wide(), this, 0, 6, 0, 0));
        liveThinkBox.setVisibility(View.GONE);
        c.addView(liveThinkBox, Ui.margins(Ui.wide(), this, 0, 0, 0, 8));

        liveStatus = Ui.text(this, "Waiting for " + cfg.model() + "…", 12.0f, Ui.FAINT, false);
        c.addView(liveStatus, Ui.wide());

        liveText = Ui.text(this, "", 15.0f, Ui.TEXT, false);
        liveText.setTextIsSelectable(true);
        c.addView(liveText, Ui.wide());

        into.addView(c, Ui.margins(Ui.wide(), this, 0, 4, 36, 8));

        // Adopt whatever has already arrived, so a rebuild mid-reply keeps it.
        String a;
        String t;
        synchronized (lock) {
            a = liveAnswer.toString();
            t = liveThink.toString();
        }
        applyLive(a, t);
    }

    // ------------------------------------------------------------- markdown

    /** Renders reply text as a stack of views, one per Markdown block. */
    private void renderMarkdown(LinearLayout into, String text) {
        List<Markdown.Block> blocks = Markdown.parse(text);
        if (blocks.isEmpty()) {
            TextView t = Ui.text(this, text == null ? "" : text, 15.0f, Ui.TEXT, false);
            t.setTextIsSelectable(true);
            into.addView(t, Ui.wide());
            return;
        }
        for (int i = 0; i < blocks.size(); i++) {
            Markdown.Block b = blocks.get(i);
            float top = i == 0 ? 0 : 8;
            if (b.kind == Markdown.CODE) {
                into.addView(codeBlock(b), Ui.margins(Ui.wide(), this, 0, top, 0, 2));
            } else if (b.kind == Markdown.HEADING) {
                TextView t = Ui.text(this, b.text, 16.5f, Ui.TEXT, true);
                t.setTextIsSelectable(true);
                into.addView(t, Ui.margins(Ui.wide(), this, 0, top + 2, 0, 0));
            } else if (b.kind == Markdown.BULLET) {
                LinearLayout r = Ui.row(this);
                r.setGravity(Gravity.TOP);
                r.addView(Ui.text(this, "•", 15.0f, Ui.ACCENT, true), Ui.wrap());
                TextView t = Ui.text(this, b.text, 15.0f, Ui.TEXT, false);
                t.setTextIsSelectable(true);
                r.addView(t, Ui.margins(Ui.grow(), this, 8, 0, 0, 0));
                into.addView(r, Ui.margins(Ui.wide(), this, 0, i == 0 ? 0 : 4, 0, 0));
            } else if (b.kind == Markdown.QUOTE) {
                LinearLayout q = Ui.col(this);
                q.setBackground(Ui.panel(this, Ui.BG, 8));
                q.setPadding(Ui.dp(this, 10), Ui.dp(this, 8), Ui.dp(this, 10), Ui.dp(this, 8));
                TextView t = Ui.text(this, b.text, 14.0f, Ui.MUTED, false);
                t.setTextIsSelectable(true);
                q.addView(t, Ui.wide());
                into.addView(q, Ui.margins(Ui.wide(), this, 0, top, 0, 2));
            } else {
                TextView t = Ui.text(this, b.text, 15.0f, Ui.TEXT, false);
                t.setTextIsSelectable(true);
                into.addView(t, Ui.margins(Ui.wide(), this, 0, top, 0, 0));
            }
        }
    }

    /**
     * A code block: monospaced, on a dark card, scrolling sideways rather than
     * wrapping, because wrapped code is hard to read.
     */
    private View codeBlock(Markdown.Block b) {
        LinearLayout wrap = Ui.col(this);
        wrap.setBackground(Ui.panel(this, Ui.CODE_BG, 10));
        wrap.setPadding(Ui.dp(this, 10), Ui.dp(this, 8), Ui.dp(this, 10), Ui.dp(this, 10));
        if (b.lang != null) {
            wrap.addView(Ui.mono(this, b.lang, 11.0f, Ui.alpha(Ui.CODE_TEXT, 0x99)), Ui.wide());
        }
        HorizontalScrollView h = new HorizontalScrollView(this);
        TextView code = Ui.mono(this, b.text, 13.0f, Ui.CODE_TEXT);
        code.setTextIsSelectable(true);
        h.addView(code, new LinearLayout.LayoutParams(ViewGroup.LayoutParams.WRAP_CONTENT,
                ViewGroup.LayoutParams.WRAP_CONTENT));
        wrap.addView(h, Ui.margins(Ui.wide(), this, 0, b.lang == null ? 0 : 4, 0, 0));
        return wrap;
    }

    // ------------------------------------------------------------- streaming

    private void send() {
        String text = input.getText() == null ? "" : input.getText().toString().trim();
        if (text.isEmpty()) {
            return;
        }
        if (!cfg.ready()) {
            toast("Add an API key in Settings first.");
            push(new SettingsScreen());
            return;
        }
        input.setText("");
        current.add(new Chat.Message(Chat.USER, text));
        current.updated = now();
        promote();
        save();
        startTurn();
    }

    /** Moves the open conversation to the top of the list. */
    private void promote() {
        chats.remove(current);
        chats.add(0, current);
    }

    private void retryFrom(int index) {
        if (call != null) {
            return;
        }
        // Drop the failed turn (and anything after it) and ask again.
        while (current.messages.size() > index) {
            current.messages.remove(current.messages.size() - 1);
        }
        save();
        if (lastIsUser()) {
            startTurn();
        } else {
            show();
        }
    }

    private boolean lastIsUser() {
        if (current.messages.isEmpty()) {
            return false;
        }
        return current.messages.get(current.messages.size() - 1).role.equals(Chat.USER);
    }

    private void startTurn() {
        synchronized (lock) {
            liveAnswer.setLength(0);
            liveThink.setLength(0);
        }
        final Net.Params params = cfg.params();
        final List<Object> messages = Chat.wire(current, cfg.systemPrompt(), cfg.history());
        final Net.Call mine = new Net.Call();
        call = mine;
        sendView.setText("Stop");
        show();

        worker.execute(new Runnable() {
            public void run() {
                Net.chat(params, messages, new Net.Sink() {
                    public void delta(String t) {
                        synchronized (lock) {
                            liveAnswer.append(t);
                        }
                        schedule();
                    }

                    public void reasoning(String t) {
                        synchronized (lock) {
                            liveThink.append(t);
                        }
                        schedule();
                    }

                    public void done(String finishReason) {
                        finishTurn(mine, null, finishReason);
                    }

                    public void failed(String message) {
                        finishTurn(mine, message, null);
                    }
                }, mine);
            }
        });
    }

    /** Called from the worker thread; coalesces redraws onto the UI thread. */
    private void schedule() {
        if (flushPending) {
            return;
        }
        flushPending = true;
        runOnUiThread(new Runnable() {
            public void run() {
                shell.postDelayed(flusher, FLUSH_MS);
            }
        });
    }

    private final Runnable flusher = new Runnable() {
        public void run() {
            flushPending = false;
            String a;
            String t;
            synchronized (lock) {
                a = liveAnswer.toString();
                t = liveThink.toString();
            }
            applyLive(a, t);
        }
    };

    private void applyLive(String answer, String trace) {
        boolean wasAtBottom = atBottom();
        if (liveThinkBox != null) {
            liveThinkBox.setVisibility(trace.isEmpty() ? View.GONE : View.VISIBLE);
        }
        if (liveThinkText != null && !trace.isEmpty()) {
            liveThinkText.setText(trace.trim());
        }
        if (liveStatus != null) {
            liveStatus.setVisibility(answer.isEmpty() && trace.isEmpty()
                    ? View.VISIBLE : View.GONE);
        }
        if (liveText != null) {
            liveText.setText(answer);
            liveText.setVisibility(answer.isEmpty() ? View.GONE : View.VISIBLE);
        }
        if (wasAtBottom) {
            scrollToBottom();
        }
    }

    /** Is the transcript scrolled to (or near) the newest message? */
    private boolean atBottom() {
        if (scroller == null || content == null) {
            return true;
        }
        int slack = Ui.dp(this, 140);
        return content.getHeight() - scroller.getScrollY() - scroller.getHeight() <= slack;
    }

    /** Posted, so the scroll happens after the new text has been laid out. */
    private void scrollToBottom() {
        if (scroller == null) {
            return;
        }
        scroller.post(new Runnable() {
            public void run() {
                int max = content.getHeight() - scroller.getHeight();
                scroller.scrollTo(0, max > 0 ? max : 0);
            }
        });
    }

    private void finishTurn(final Net.Call mine, final String error, final String finishReason) {
        runOnUiThread(new Runnable() {
            public void run() {
                if (mine != call) {
                    return; // cancelled, or superseded by a newer turn
                }
                call = null;
                sendView.setText("Send");
                String answer;
                String trace;
                synchronized (lock) {
                    answer = liveAnswer.toString().trim();
                    trace = liveThink.toString().trim();
                }
                if (!answer.isEmpty() || !trace.isEmpty()) {
                    Chat.Message m = new Chat.Message(Chat.ASSISTANT, answer,
                            trace.isEmpty() ? null : trace);
                    if (answer.isEmpty()) {
                        // A trace but no answer: say so rather than showing a blank.
                        m.text = "(the model returned only a reasoning trace)";
                    }
                    current.add(m);
                }
                if (error != null) {
                    Chat.Message e = new Chat.Message(Chat.ASSISTANT, error);
                    e.failed = true;
                    current.add(e);
                } else if ("length".equals(finishReason)) {
                    Chat.Message e = new Chat.Message(Chat.ASSISTANT,
                            "The reply was cut off by the token limit. Raise “Max tokens” "
                            + "in Settings, or ask for a shorter answer.");
                    e.failed = true;
                    current.add(e);
                }
                current.updated = now();
                save();
                show();
            }
        });
    }

    /** Stop button: keep whatever arrived, and drop the connection. */
    private void stop() {
        if (call == null) {
            return;
        }
        Net.Call mine = call;
        call = null; // the worker's completion is now stale and will be ignored
        mine.cancel();
        sendView.setText("Send");
        String answer;
        String trace;
        synchronized (lock) {
            answer = liveAnswer.toString().trim();
            trace = liveThink.toString().trim();
        }
        if (!answer.isEmpty()) {
            current.add(new Chat.Message(Chat.ASSISTANT, answer,
                    trace.isEmpty() ? null : trace));
            current.updated = now();
            save();
        }
        show();
    }

    // ------------------------------------------------------------ chats screen

    private final class ChatsScreen extends Screen {
        String title() {
            return "Chats";
        }

        String action() {
            return "New";
        }

        void onAction() {
            if (call != null) {
                toast("Wait for the current reply, or stop it first.");
                return;
            }
            Chat.Conversation c = new Chat.Conversation(now());
            c.updated = now();
            chats.add(0, c);
            current = c;
            save();
            stack.remove(stack.size() - 1);
            show();
        }

        void build(LinearLayout into) {
            Chat.sort(chats);
            LinearLayout card = Ui.col(MainActivity.this);
            card.setBackground(Ui.panel(MainActivity.this, Ui.CARD, 14));
            for (int i = 0; i < chats.size(); i++) {
                final Chat.Conversation c = chats.get(i);
                if (i > 0) {
                    card.addView(Ui.divider(MainActivity.this),
                            Ui.dividerParams(MainActivity.this));
                }
                int turns = c.messages.size();
                String sub = turns == 0 ? "Empty"
                        : turns + (turns == 1 ? " message" : " messages");
                if (c == current) {
                    sub = sub + "  ·  open";
                }
                LinearLayout row = Ui.settingRow(MainActivity.this, c.title(), sub);
                row.setOnClickListener(new View.OnClickListener() {
                    public void onClick(View v) {
                        if (call != null) {
                            toast("Wait for the current reply, or stop it first.");
                            return;
                        }
                        current = c;
                        stack.remove(stack.size() - 1);
                        show();
                    }
                });
                row.setOnLongClickListener(new View.OnLongClickListener() {
                    public boolean onLongClick(View v) {
                        confirmDelete(c);
                        return true;
                    }
                });
                card.addView(row, Ui.wide());
            }
            into.addView(card, Ui.wide());
            into.addView(Ui.text(MainActivity.this, "Press and hold a chat to delete it.",
                    12.0f, Ui.FAINT, false), Ui.margins(Ui.wide(), MainActivity.this, 4, 10, 0, 0));

            TextView settings = Ui.button(MainActivity.this, "Settings", Ui.CARD, Ui.ACCENT);
            settings.setBackground(Ui.outline(MainActivity.this, Ui.CARD, Ui.LINE, 12));
            settings.setOnClickListener(new View.OnClickListener() {
                public void onClick(View v) {
                    push(new SettingsScreen());
                }
            });
            into.addView(settings, Ui.margins(Ui.wide(), MainActivity.this, 0, 16, 0, 0));
        }
    }

    private void confirmDelete(final Chat.Conversation c) {
        Ui.dialog(this)
                .setTitle("Delete this chat?")
                .setMessage(c.title())
                .setNegativeButton("Cancel", null)
                .setPositiveButton("Delete", new android.content.DialogInterface.OnClickListener() {
                    public void onClick(android.content.DialogInterface d, int w) {
                        if (call != null && c == current) {
                            call.cancel();
                            call = null;
                            sendView.setText("Send");
                        }
                        chats.remove(c);
                        if (chats.isEmpty()) {
                            chats.add(new Chat.Conversation(now()));
                        }
                        if (c == current) {
                            current = chats.get(0);
                        }
                        save();
                        show();
                    }
                })
                .show();
    }

    // --------------------------------------------------------- settings screen

    private final class SettingsScreen extends Screen {
        String title() {
            return "Settings";
        }

        void build(LinearLayout into) {
            into.addView(sectionLabel("Endpoint"), Ui.wide());
            LinearLayout a = group();
            addRow(a, "API key", Ui.mask(cfg.apiKey()), new Runnable() {
                public void run() {
                    editKey();
                }
            }, true);
            addRow(a, "Base URL", cfg.baseUrl(), new Runnable() {
                public void run() {
                    editBaseUrl();
                }
            }, true);
            addRow(a, "Model", cfg.model(), new Runnable() {
                public void run() {
                    pickModel();
                }
            }, false);
            into.addView(a, Ui.wide());

            into.addView(sectionLabel("Generation"), Ui.wide());
            LinearLayout b = group();
            addRow(b, "System prompt", describePrompt(), new Runnable() {
                public void run() {
                    editSystemPrompt();
                }
            }, true);
            addRow(b, "Temperature", fmt(cfg.temperature()), new Runnable() {
                public void run() {
                    editTemperature();
                }
            }, true);
            addRow(b, "Max tokens",
                    cfg.maxTokens() == 0 ? "Server default" : String.valueOf(cfg.maxTokens()),
                    new Runnable() {
                        public void run() {
                            editMaxTokens();
                        }
                    }, true);
            addRow(b, "History sent",
                    cfg.history() == 0 ? "Whole conversation"
                            : "Last " + cfg.history() + " messages",
                    new Runnable() {
                        public void run() {
                            editHistory();
                        }
                    }, false);
            into.addView(b, Ui.wide());

            into.addView(sectionLabel("Display"), Ui.wide());
            LinearLayout c = group();
            addRow(c, "Stream replies", cfg.stream() ? "On — token by token" : "Off",
                    new Runnable() {
                        public void run() {
                            cfg.setStream(!cfg.stream());
                            show();
                        }
                    }, true);
            addRow(c, "Expand reasoning",
                    cfg.showReasoning() ? "Traces start open" : "Traces start collapsed",
                    new Runnable() {
                        public void run() {
                            cfg.setShowReasoning(!cfg.showReasoning());
                            traceOpen = cfg.showReasoning();
                            show();
                        }
                    }, false);
            into.addView(c, Ui.wide());

            if (!cfg.baseUrl().toLowerCase().startsWith("https://")) {
                LinearLayout warn = Ui.card(MainActivity.this, Ui.ERR_BG);
                warn.addView(Ui.text(MainActivity.this,
                        "This base URL isn't HTTPS. Android blocks plain HTTP for this app, "
                        + "so requests will fail. Use an https:// address.",
                        12.5f, Ui.ERR, false), Ui.wide());
                into.addView(warn, Ui.margins(Ui.wide(), MainActivity.this, 0, 14, 0, 0));
            }

            TextView about = Ui.text(MainActivity.this,
                    "Hermes " + Defaults.VERSION + " · built with droidforge\n"
                    + "The key is stored in this app's private settings, unencrypted. "
                    + "Anyone with access to the unlocked phone, or to a rooted one, can read it.",
                    11.5f, Ui.FAINT, false);
            into.addView(about, Ui.margins(Ui.wide(), MainActivity.this, 4, 18, 4, 0));
        }

        private String describePrompt() {
            String p = cfg.systemPrompt().trim();
            if (p.isEmpty()) {
                return "None";
            }
            if (p.equals(Defaults.REASONING_PROMPT)) {
                return "Deep thinking preset";
            }
            return p.length() > 38 ? p.substring(0, 38).replace('\n', ' ') + "…" : p;
        }
    }

    private TextView sectionLabel(String s) {
        TextView t = Ui.text(this, s.toUpperCase(), 11.5f, Ui.FAINT, true);
        t.setLetterSpacing(0.08f);
        t.setPadding(Ui.dp(this, 4), Ui.dp(this, 16), 0, Ui.dp(this, 6));
        return t;
    }

    private LinearLayout group() {
        LinearLayout l = Ui.col(this);
        l.setBackground(Ui.panel(this, Ui.CARD, 14));
        return l;
    }

    private void addRow(LinearLayout into, String label, String value,
                        final Runnable onTap, boolean divider) {
        LinearLayout row = Ui.settingRow(this, label, value);
        row.setOnClickListener(new View.OnClickListener() {
            public void onClick(View v) {
                onTap.run();
            }
        });
        into.addView(row, Ui.wide());
        if (divider) {
            into.addView(Ui.divider(this), Ui.dividerParams(this));
        }
    }

    private static String fmt(double v) {
        long whole = (long) v;
        if (v == (double) whole) {
            return whole + ".0";
        }
        String s = String.valueOf(v);
        return s.length() > 4 ? s.substring(0, 4) : s;
    }

    // ----------------------------------------------------------- settings edits

    /** A dialog with one text field. */
    private EditText field(String value, int inputType, String hint) {
        EditText e = new EditText(this);
        e.setText(value == null ? "" : value);
        e.setHint(hint);
        e.setHintTextColor(Ui.FAINT);
        e.setTextColor(Ui.TEXT);
        e.setTextSize(15.0f);
        e.setInputType(inputType);
        int p = Ui.dp(this, 10);
        e.setPadding(p, p, p, p);
        return e;
    }

    private void editKey() {
        final EditText e = field(cfg.apiKey(), InputType.TYPE_CLASS_TEXT
                | InputType.TYPE_TEXT_FLAG_NO_SUGGESTIONS, "sk-…");
        Ui.dialog(this)
                .setTitle("API key")
                .setMessage("Sent as an Authorization: Bearer header.")
                .setView(e)
                .setNegativeButton("Cancel", null)
                .setPositiveButton("Save", new android.content.DialogInterface.OnClickListener() {
                    public void onClick(android.content.DialogInterface d, int w) {
                        cfg.setApiKey(text(e));
                        show();
                    }
                })
                .show();
    }

    private void editBaseUrl() {
        final EditText e = field(cfg.baseUrl(), InputType.TYPE_CLASS_TEXT
                | InputType.TYPE_TEXT_FLAG_NO_SUGGESTIONS, Defaults.BASE_URL);
        Ui.dialog(this)
                .setTitle("Base URL")
                .setMessage("Any OpenAI-compatible endpoint. /chat/completions is appended.")
                .setView(e)
                .setNegativeButton("Cancel", null)
                .setNeutralButton("Default",
                        new android.content.DialogInterface.OnClickListener() {
                            public void onClick(android.content.DialogInterface d, int w) {
                                cfg.setBaseUrl(Defaults.BASE_URL);
                                show();
                            }
                        })
                .setPositiveButton("Save", new android.content.DialogInterface.OnClickListener() {
                    public void onClick(android.content.DialogInterface d, int w) {
                        cfg.setBaseUrl(text(e));
                        show();
                    }
                })
                .show();
    }

    private void editSystemPrompt() {
        final EditText e = field(cfg.systemPrompt(), InputType.TYPE_CLASS_TEXT
                | InputType.TYPE_TEXT_FLAG_MULTI_LINE, "Optional instructions…");
        e.setMaxLines(8);
        Ui.dialog(this)
                .setTitle("System prompt")
                .setMessage("Sent before the conversation. “Thinking” asks Hermes to "
                        + "reason in <think> tags, which this app shows separately.")
                .setView(e)
                .setNegativeButton("Cancel", null)
                .setNeutralButton("Thinking",
                        new android.content.DialogInterface.OnClickListener() {
                            public void onClick(android.content.DialogInterface d, int w) {
                                cfg.setSystemPrompt(Defaults.REASONING_PROMPT);
                                show();
                            }
                        })
                .setPositiveButton("Save", new android.content.DialogInterface.OnClickListener() {
                    public void onClick(android.content.DialogInterface d, int w) {
                        cfg.setSystemPrompt(text(e));
                        show();
                    }
                })
                .show();
    }

    private void editTemperature() {
        final EditText e = field(fmt(cfg.temperature()), InputType.TYPE_CLASS_NUMBER
                | InputType.TYPE_NUMBER_FLAG_DECIMAL, "0.7");
        Ui.dialog(this)
                .setTitle("Temperature")
                .setMessage("0 is nearly deterministic, 1 is lively. Range 0–2.")
                .setView(e)
                .setNegativeButton("Cancel", null)
                .setPositiveButton("Save", new android.content.DialogInterface.OnClickListener() {
                    public void onClick(android.content.DialogInterface d, int w) {
                        try {
                            double v = Double.parseDouble(text(e));
                            if (v < 0.0 || v > 2.0) {
                                toast("Temperature must be between 0 and 2.");
                            } else {
                                cfg.setTemperature(v);
                            }
                        } catch (NumberFormatException nfe) {
                            toast("That isn't a number.");
                        }
                        show();
                    }
                })
                .show();
    }

    private void editMaxTokens() {
        final EditText e = field(cfg.maxTokens() == 0 ? "" : String.valueOf(cfg.maxTokens()),
                InputType.TYPE_CLASS_NUMBER, "server default");
        Ui.dialog(this)
                .setTitle("Max tokens")
                .setMessage("The longest reply to allow. Leave empty to let the server decide.")
                .setView(e)
                .setNegativeButton("Cancel", null)
                .setPositiveButton("Save", new android.content.DialogInterface.OnClickListener() {
                    public void onClick(android.content.DialogInterface d, int w) {
                        String s = text(e);
                        if (s.isEmpty()) {
                            cfg.setMaxTokens(0);
                        } else {
                            try {
                                cfg.setMaxTokens(Integer.parseInt(s));
                            } catch (NumberFormatException nfe) {
                                toast("That isn't a whole number.");
                            }
                        }
                        show();
                    }
                })
                .show();
    }

    private void editHistory() {
        final EditText e = field(cfg.history() == 0 ? "" : String.valueOf(cfg.history()),
                InputType.TYPE_CLASS_NUMBER, "24");
        Ui.dialog(this)
                .setTitle("History sent")
                .setMessage("How many past messages go with each turn. The whole history is "
                        + "re-sent every time, so a lower number costs less. Empty means all.")
                .setView(e)
                .setNegativeButton("Cancel", null)
                .setPositiveButton("Save", new android.content.DialogInterface.OnClickListener() {
                    public void onClick(android.content.DialogInterface d, int w) {
                        String s = text(e);
                        if (s.isEmpty()) {
                            cfg.setHistory(0);
                        } else {
                            try {
                                cfg.setHistory(Integer.parseInt(s));
                            } catch (NumberFormatException nfe) {
                                toast("That isn't a whole number.");
                            }
                        }
                        show();
                    }
                })
                .show();
    }

    private static String text(EditText e) {
        return e.getText() == null ? "" : e.getText().toString().trim();
    }

    // -------------------------------------------------------------- model pick

    /** Offers the built-in suggestions, the endpoint's own list, or free text. */
    private void pickModel() {
        final List<String> options = Net.suggestions();
        if (!options.contains(cfg.model())) {
            options.add(0, cfg.model());
        }
        final CharSequence[] items = new CharSequence[options.size() + 2];
        for (int i = 0; i < options.size(); i++) {
            items[i] = (options.get(i).equals(cfg.model()) ? "✓  " : "    ")
                    + options.get(i);
        }
        items[options.size()] = "Ask the endpoint for its list…";
        items[options.size() + 1] = "Type a model id…";

        Ui.dialog(this)
                .setTitle("Model")
                .setItems(items, new android.content.DialogInterface.OnClickListener() {
                    public void onClick(android.content.DialogInterface d, int which) {
                        if (which < options.size()) {
                            cfg.setModel(options.get(which));
                            show();
                        } else if (which == options.size()) {
                            fetchModels();
                        } else {
                            typeModel();
                        }
                    }
                })
                .setNegativeButton("Cancel", null)
                .show();
    }

    private void typeModel() {
        final EditText e = field(cfg.model(), InputType.TYPE_CLASS_TEXT
                | InputType.TYPE_TEXT_FLAG_NO_SUGGESTIONS, Defaults.MODEL);
        Ui.dialog(this)
                .setTitle("Model id")
                .setView(e)
                .setNegativeButton("Cancel", null)
                .setPositiveButton("Save", new android.content.DialogInterface.OnClickListener() {
                    public void onClick(android.content.DialogInterface d, int w) {
                        if (!text(e).isEmpty()) {
                            cfg.setModel(text(e));
                        }
                        show();
                    }
                })
                .show();
    }

    /** Asks {@code GET /models} what this key can actually reach. */
    private void fetchModels() {
        toast("Asking the endpoint for its models…");
        final Net.Params p = cfg.params();
        worker.execute(new Runnable() {
            public void run() {
                List<String> ids = null;
                String error = null;
                try {
                    ids = Net.models(p);
                } catch (Net.ApiException e) {
                    error = e.getMessage(); // already phrased for a person
                } catch (IOException e) {
                    error = Net.ioError(e, p.baseUrl);
                } catch (RuntimeException e) {
                    error = "Couldn't read the model list.";
                }
                final List<String> got = ids;
                final String failure = error;
                runOnUiThread(new Runnable() {
                    public void run() {
                        if (got == null) {
                            Ui.dialog(MainActivity.this)
                                    .setTitle("Couldn't list models")
                                    .setMessage(failure)
                                    .setPositiveButton("OK", null)
                                    .show();
                            return;
                        }
                        showModelList(got);
                    }
                });
            }
        });
    }

    private void showModelList(final List<String> ids) {
        // Hermes models first: on a gateway the list can run to hundreds.
        final List<String> sorted = new ArrayList<String>();
        for (int i = 0; i < ids.size(); i++) {
            if (ids.get(i).toLowerCase().indexOf("hermes") >= 0) {
                sorted.add(ids.get(i));
            }
        }
        int hermes = sorted.size();
        for (int i = 0; i < ids.size(); i++) {
            if (!sorted.contains(ids.get(i))) {
                sorted.add(ids.get(i));
            }
        }
        final CharSequence[] items = new CharSequence[sorted.size()];
        for (int i = 0; i < sorted.size(); i++) {
            items[i] = sorted.get(i);
        }
        Ui.dialog(this)
                .setTitle(hermes > 0 ? sorted.size() + " models · Hermes first"
                        : sorted.size() + " models")
                .setItems(items, new android.content.DialogInterface.OnClickListener() {
                    public void onClick(android.content.DialogInterface d, int which) {
                        cfg.setModel(sorted.get(which));
                        show();
                    }
                })
                .setNegativeButton("Cancel", null)
                .show();
    }
}
