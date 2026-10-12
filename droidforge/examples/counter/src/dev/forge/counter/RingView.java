package dev.forge.counter;

import android.content.Context;
import android.graphics.Canvas;
import android.graphics.Color;
import android.graphics.Paint;
import android.graphics.RectF;
import android.graphics.Typeface;
import android.view.View;

/** Custom-drawn progress ring with an animated count in the middle. */
public class RingView extends View {
    private final Paint track = new Paint(Paint.ANTI_ALIAS_FLAG);
    private final Paint arc = new Paint(Paint.ANTI_ALIAS_FLAG);
    private final Paint big = new Paint(Paint.ANTI_ALIAS_FLAG);
    private final Paint small = new Paint(Paint.ANTI_ALIAS_FLAG);
    private final RectF box = new RectF();
    private final float density;
    private int count;
    private int goal = 25;
    private float shown;          // animated value shown by the ring

    public RingView(Context context) {
        super(context);
        density = context.getResources().getDisplayMetrics().density;
        track.setStyle(Paint.Style.STROKE);
        track.setColor(Color.parseColor("#2C3A5C"));
        arc.setStyle(Paint.Style.STROKE);
        arc.setStrokeCap(Paint.Cap.ROUND);
        arc.setColor(Color.parseColor("#FFB547"));
        big.setColor(Color.WHITE);
        big.setTextAlign(Paint.Align.CENTER);
        big.setTypeface(Typeface.create(Typeface.DEFAULT, Typeface.BOLD));
        small.setColor(Color.parseColor("#9AA8C7"));
        small.setTextAlign(Paint.Align.CENTER);
    }

    public void setValues(int count, int goal) {
        this.count = count;
        this.goal = goal;
        invalidate();
    }

    @Override
    protected void onDraw(Canvas canvas) {
        float w = getWidth(), h = getHeight();
        float size = Math.min(w, h) * 0.8f;
        float stroke = 18 * density;
        track.setStrokeWidth(stroke);
        arc.setStrokeWidth(stroke);
        float cx = w / 2f, cy = h / 2f;
        box.set(cx - size / 2, cy - size / 2, cx + size / 2, cy + size / 2);
        canvas.drawArc(box, 0, 360, false, track);

        shown += (count - shown) * 0.2f;
        if (Math.abs(count - shown) < 0.01f) shown = count;
        float frac = goal > 0 ? Math.min(shown / goal, 1f) : 0f;
        if (count >= goal) arc.setColor(Color.parseColor("#6BE38A"));
        else arc.setColor(Color.parseColor("#FFB547"));
        if (frac > 0) canvas.drawArc(box, -90, 360 * frac, false, arc);

        big.setTextSize(size * 0.32f);
        canvas.drawText(String.valueOf(Math.round(shown)), cx, cy + big.getTextSize() * 0.35f, big);
        small.setTextSize(size * 0.075f);
        String sub = count >= goal ? "goal reached!" : "of " + goal + "  ·  tap to change";
        canvas.drawText(sub, cx, cy + size * 0.25f, small);

        if (shown != count) postInvalidateOnAnimation();
    }
}
