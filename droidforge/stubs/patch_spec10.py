"""Tenth stub pass (OPEN CRM): date picker, FLAG_SECURE, ACTION_SENDTO."""
import os
here = os.path.dirname(os.path.abspath(__file__))
spec_path = os.path.join(here, "spec_content.txt")
src = open(spec_path).read()
if "android/app/DatePickerDialog.java" in src:
    print("already patched")
    raise SystemExit(0)
src = src.replace(
    '        public static final int FLAG_FULLSCREEN = 1024;\n',
    '        public static final int FLAG_FULLSCREEN = 1024;\n'
    '        public static final int FLAG_SECURE = 8192;\n', 1)
src = src.replace(
    '    public static final String ACTION_SEND = "android.intent.action.SEND";\n',
    '    public static final String ACTION_SEND = "android.intent.action.SEND";\n'
    '    public static final String ACTION_SENDTO = "android.intent.action.SENDTO";\n', 1)
src = src.rstrip("\n") + "\n" + '''//// android/widget/DatePicker.java
package android.widget;
public class DatePicker extends FrameLayout {
    public DatePicker(android.content.Context context) { super(context); throw new RuntimeException("Stub!"); }
    public int getYear() STUB
    public int getMonth() STUB
    public int getDayOfMonth() STUB
}
//// android/app/DatePickerDialog.java
package android.app;
import android.content.Context;
import android.widget.DatePicker;
public class DatePickerDialog extends AlertDialog {
    public DatePickerDialog(Context context, OnDateSetListener listener, int year,
                            int month, int dayOfMonth) { super(context); throw new RuntimeException("Stub!"); }
    public void setButton(int whichButton, CharSequence text, android.content.DialogInterface.OnClickListener listener) STUB
    public DatePicker getDatePicker() STUB
    public interface OnDateSetListener {
        void onDateSet(DatePicker view, int year, int month, int dayOfMonth);
    }
}
'''
open(spec_path, "w").write(src)
print("patched")
