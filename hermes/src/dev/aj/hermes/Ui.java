package dev.aj.hermes;

import android.content.Context;
import android.graphics.Typeface;
import android.graphics.drawable.GradientDrawable;
import android.view.Gravity;
import android.view.View;
import android.view.ViewGroup;
import android.widget.LinearLayout;
import android.widget.TextView;

/**
 * Colours and view factories. droidforge compiles no layout XML, so the whole
 * interface is assembled in code.
 *
 * Light, for the same reason the rest of this toolchain's apps are: at
 * minSdk 24 the platform theme is DeviceDefault.Light, so the alert dialogs
 * and the keyboard draw for a light background. A dark chat window with light
 * system dialogs on top of it looks broken, and there is no AppCompat here to
 * theme them with.
 */
final class Ui {

    static final int BG = 0xFFF4F5F8;
    static final int CARD = 0xFFFFFFFF;
    static final int LINE = 0xFFDFE3EA;
    static final int TEXT = 0xFF141821;
    static final int MUTED = 0xFF5A6472;
    static final int FAINT = 0xFF8B95A3;

    /** Hermes violet: the accent, used for the send button and the user's turns. */
    static final int ACCENT = 0xFF5B4BD6;
    static final int ACCENT_SOFT = 0xFFEDEAFD;
    static final int ACCENT_DEEP = 0xFF2E2470;

    /** The reasoning trace: present but recessive. */
    static final int THINK_BG = 0xFFF7F5FF;
    static final int THINK_TEXT = 0xFF4B4080;

    static final int CODE_BG = 0xFF1E2230;
    static final int CODE_TEXT = 0xFFE6E9F2;

    static final int ERR = 0xFFC62828;
    static final int ERR_BG = 0xFFFDECEC;
    static final int OK = 0xFF1B8546;

    private Ui() {
    }

    static int dp(Context c, float v) {
        float d = 2.0f;
        try {
            float got = c.getResources().getDisplayMetrics().density;
            if (got > 0.0f) {
                d = got;
            }
        } catch (Throwable t) {
            // keep the default; a missing density must not stop the app drawing
        }
        return (int) (v * d + 0.5f);
    }

    /** Dialogs get an explicit light theme so they match the app everywhere. */
    static android.app.AlertDialog.Builder dialog(Context c) {
        return new android.app.AlertDialog.Builder(c,
                android.app.AlertDialog.THEME_DEVICE_DEFAULT_LIGHT);
    }

    static TextView text(Context c, String s, float size, int colour, boolean bold) {
        TextView t = new TextView(c);
        t.setText(s);
        t.setTextSize(size);
        t.setTextColor(colour);
        if (bold) {
            t.setTypeface(Typeface.DEFAULT_BOLD);
        }
        t.setLineSpacing(0.0f, 1.15f);
        return t;
    }

    static TextView mono(Context c, String s, float size, int colour) {
        TextView t = text(c, s, size, colour, false);
        t.setTypeface(Typeface.MONOSPACE);
        t.setLineSpacing(0.0f, 1.08f);
        return t;
    }

    static LinearLayout col(Context c) {
        LinearLayout l = new LinearLayout(c);
        l.setOrientation(LinearLayout.VERTICAL);
        return l;
    }

    static LinearLayout row(Context c) {
        LinearLayout l = new LinearLayout(c);
        l.setOrientation(LinearLayout.HORIZONTAL);
        l.setGravity(Gravity.CENTER_VERTICAL);
        return l;
    }

    static GradientDrawable panel(Context c, int fill, float radiusDp) {
        GradientDrawable g = new GradientDrawable();
        g.setColor(fill);
        g.setCornerRadius(dp(c, radiusDp));
        return g;
    }

    static GradientDrawable outline(Context c, int fill, int stroke, float radiusDp) {
        GradientDrawable g = panel(c, fill, radiusDp);
        g.setStroke(Math.max(1, dp(c, 1)), stroke);
        return g;
    }

    /** A rounded card, padded, ready to have content added. */
    static LinearLayout card(Context c, int fill) {
        LinearLayout l = col(c);
        l.setBackground(panel(c, fill, 14));
        int p = dp(c, 13);
        l.setPadding(p, dp(c, 11), p, dp(c, 11));
        return l;
    }

    /** A tappable settings row: label on the left, current value on the right. */
    static LinearLayout settingRow(Context c, String label, String value) {
        LinearLayout r = row(c);
        r.setPadding(dp(c, 14), dp(c, 13), dp(c, 14), dp(c, 13));
        LinearLayout texts = col(c);
        texts.addView(text(c, label, 15.0f, TEXT, false));
        if (value != null && !value.isEmpty()) {
            TextView v = text(c, value, 12.5f, MUTED, false);
            v.setMaxLines(2);
            texts.addView(v, margins(wide(), c, 0, 2, 0, 0));
        }
        r.addView(texts, grow());
        r.addView(text(c, "›", 19.0f, FAINT, false));
        r.setClickable(true);
        return r;
    }

    /**
     * A 1dp separator view. GradientDrawable has no per-edge stroke, so rows
     * are separated by stacking one of these rather than by a row background.
     */
    static View divider(Context c) {
        View v = new View(c);
        v.setBackgroundColor(LINE);
        return v;
    }

    static LinearLayout.LayoutParams dividerParams(Context c) {
        LinearLayout.LayoutParams p = new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, Math.max(1, dp(c, 0.6f)));
        p.leftMargin = dp(c, 14);
        return p;
    }

    /** The primary button: a filled, rounded, centred label. */
    static TextView button(Context c, String label, int fill, int colour) {
        TextView t = text(c, label, 15.0f, colour, true);
        t.setGravity(Gravity.CENTER);
        t.setBackground(panel(c, fill, 12));
        t.setPadding(dp(c, 18), dp(c, 12), dp(c, 18), dp(c, 12));
        t.setClickable(true);
        return t;
    }

    static int alpha(int colour, int a) {
        return (colour & 0x00FFFFFF) | ((a & 0xFF) << 24);
    }

    static LinearLayout.LayoutParams wide() {
        return new LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT,
                ViewGroup.LayoutParams.WRAP_CONTENT);
    }

    static LinearLayout.LayoutParams wrap() {
        return new LinearLayout.LayoutParams(ViewGroup.LayoutParams.WRAP_CONTENT,
                ViewGroup.LayoutParams.WRAP_CONTENT);
    }

    static LinearLayout.LayoutParams grow() {
        return new LinearLayout.LayoutParams(0, ViewGroup.LayoutParams.WRAP_CONTENT, 1.0f);
    }

    static LinearLayout.LayoutParams fill() {
        return new LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, 0, 1.0f);
    }

    static LinearLayout.LayoutParams margins(LinearLayout.LayoutParams p, Context c,
                                             float l, float t, float r, float b) {
        p.leftMargin = dp(c, l);
        p.topMargin = dp(c, t);
        p.rightMargin = dp(c, r);
        p.bottomMargin = dp(c, b);
        return p;
    }

    /** Hides the middle of a secret, leaving enough to recognise it. */
    static String mask(String secret) {
        if (secret == null || secret.isEmpty()) {
            return "Not set";
        }
        String s = secret.trim();
        if (s.length() <= 10) {
            return "••••••";
        }
        return s.substring(0, 5) + "…" + s.substring(s.length() - 4);
    }
}
