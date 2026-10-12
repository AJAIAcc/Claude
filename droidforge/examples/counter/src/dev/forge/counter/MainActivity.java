package dev.forge.counter;

import android.app.Activity;
import android.app.AlertDialog;
import android.content.SharedPreferences;
import android.graphics.Color;
import android.graphics.Typeface;
import android.graphics.drawable.GradientDrawable;
import android.os.Build;
import android.os.Bundle;
import android.util.TypedValue;
import android.view.Gravity;
import android.view.HapticFeedbackConstants;
import android.view.View;
import android.view.ViewGroup;
import android.view.Window;
import android.widget.LinearLayout;
import android.widget.TextView;
import android.widget.Toast;

public class MainActivity extends Activity {
    private static final int[] GOALS = {10, 25, 50, 100, 250, 1000};
    private SharedPreferences prefs;
    private RingView ring;
    private TextView info;
    private int count;
    private int goal;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        requestWindowFeature(Window.FEATURE_NO_TITLE);
        int bg = Color.parseColor("#141C30");
        getWindow().setStatusBarColor(bg);
        getWindow().setNavigationBarColor(bg);

        prefs = getSharedPreferences("counter", MODE_PRIVATE);
        count = prefs.getInt("count", 0);
        goal = prefs.getInt("goal", 25);

        LinearLayout root = new LinearLayout(this);
        root.setOrientation(LinearLayout.VERTICAL);
        root.setBackgroundColor(bg);
        root.setPadding(dp(24), dp(32), dp(24), dp(32));

        TextView title = new TextView(this);
        title.setText("Forge Counter");
        title.setTextColor(Color.WHITE);
        title.setTextSize(26);
        title.setTypeface(Typeface.create(Typeface.DEFAULT, Typeface.BOLD));
        root.addView(title);

        info = new TextView(this);
        info.setTextColor(Color.parseColor("#9AA8C7"));
        info.setTextSize(14);
        info.setText("Built on a phone-less toolchain, from first principles.");
        root.addView(info);

        ring = new RingView(this);
        ring.setOnClickListener(v -> chooseGoal());
        root.addView(ring, new LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, 0, 1f));

        LinearLayout row = new LinearLayout(this);
        row.setOrientation(LinearLayout.HORIZONTAL);
        row.setGravity(Gravity.CENTER);
        TextView minus = pill("−", "#2C3A5C", Color.WHITE);
        TextView plus = pill("+", "#FFB547", Color.parseColor("#141C30"));
        minus.setOnClickListener(v -> change(-1, v));
        plus.setOnClickListener(v -> change(+1, v));
        plus.setOnLongClickListener(v -> { change(+10, v); return true; });
        LinearLayout.LayoutParams lp = new LinearLayout.LayoutParams(0, dp(72), 1f);
        lp.setMargins(dp(8), 0, dp(8), 0);
        row.addView(minus, lp);
        row.addView(plus, new LinearLayout.LayoutParams(0, dp(72), 2f));
        ((LinearLayout.LayoutParams) plus.getLayoutParams()).setMargins(dp(8), 0, dp(8), 0);
        root.addView(row);

        TextView reset = new TextView(this);
        reset.setText("Reset");
        reset.setTextColor(Color.parseColor("#9AA8C7"));
        reset.setTextSize(15);
        reset.setGravity(Gravity.CENTER);
        reset.setPadding(0, dp(18), 0, 0);
        reset.setOnClickListener(v -> confirmReset());
        root.addView(reset);

        setContentView(root);
        refresh();
    }

    private TextView pill(String text, String color, int textColor) {
        TextView t = new TextView(this);
        t.setText(text);
        t.setTextSize(30);
        t.setTextColor(textColor);
        t.setGravity(Gravity.CENTER);
        t.setTypeface(Typeface.create(Typeface.DEFAULT, Typeface.BOLD));
        GradientDrawable d = new GradientDrawable();
        d.setColor(Color.parseColor(color));
        d.setCornerRadius(dp(36));
        t.setBackground(d);
        t.setClickable(true);
        return t;
    }

    private void change(int delta, View source) {
        int before = count;
        count = Math.max(0, count + delta);
        source.performHapticFeedback(HapticFeedbackConstants.KEYBOARD_TAP);
        if (before < goal && count >= goal) {
            source.performHapticFeedback(HapticFeedbackConstants.LONG_PRESS);
            Toast.makeText(this, "Goal of " + goal + " reached!", Toast.LENGTH_SHORT).show();
        }
        save();
        refresh();
    }

    private void chooseGoal() {
        CharSequence[] labels = new CharSequence[GOALS.length];
        for (int i = 0; i < GOALS.length; i++) labels[i] = "Goal: " + GOALS[i];
        new AlertDialog.Builder(this)
                .setTitle("Set a goal")
                .setItems(labels, (dialog, which) -> {
                    goal = GOALS[which];
                    save();
                    refresh();
                })
                .show();
    }

    private void confirmReset() {
        new AlertDialog.Builder(this)
                .setTitle("Reset counter?")
                .setMessage("This sets the count back to zero.")
                .setPositiveButton("Reset", (d, w) -> { count = 0; save(); refresh(); })
                .setNegativeButton("Cancel", null)
                .show();
    }

    private void refresh() {
        ring.setValues(count, goal);
        info.setText("Android " + Build.VERSION.RELEASE + " (API " + Build.VERSION.SDK_INT + ")  ·  long-press + for +10");
    }

    private void save() {
        prefs.edit().putInt("count", count).putInt("goal", goal).apply();
    }

    private int dp(float v) {
        return (int) TypedValue.applyDimension(TypedValue.COMPLEX_UNIT_DIP, v, getResources().getDisplayMetrics());
    }
}
