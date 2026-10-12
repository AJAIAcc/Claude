package dev.forge.resfix;

import android.app.Activity;
import android.os.Bundle;
import android.widget.LinearLayout;
import android.widget.TextView;

/** Uses generated R ids so the build proves R and the resource table agree. */
public class MainActivity extends Activity {

    /** Referenced by the verifier: these must equal the ids in resources.arsc. */
    public static final int STRING_ID = R.string.app_name;
    public static final int COLOR_ID = R.color.accent;
    public static final int XML_ID = R.xml.config;
    public static final int DRAWABLE_ID = R.drawable.dot;
    public static final int MIPMAP_ID = R.mipmap.ic_launcher;
    public static final int INT_ID = R.integer.answer;
    public static final int BOOL_ID = R.bool.feature_on;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        LinearLayout root = new LinearLayout(this);
        TextView t = new TextView(this);
        t.setText(getResources().getString(R.string.greeting));
        root.addView(t);
        setContentView(root);
    }
}
