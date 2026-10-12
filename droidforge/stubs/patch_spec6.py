"""Sixth stub pass: picking a time of day."""
import os
here = os.path.dirname(os.path.abspath(__file__))
spec_path = os.path.join(here, "spec_content.txt")
src = open(spec_path).read()
if "android/app/TimePickerDialog.java" in src:
    print("already patched")
    raise SystemExit(0)

ADDITIONS = r'''
//// android/widget/TimePicker.java
package android.widget;
public class TimePicker extends FrameLayout {
    public TimePicker(android.content.Context context) { super(context); throw new RuntimeException("Stub!"); }
    public int getHour() STUB
    public int getMinute() STUB
}
//// android/app/TimePickerDialog.java
package android.app;
import android.content.Context;
import android.widget.TimePicker;
public class TimePickerDialog extends Dialog {
    public TimePickerDialog(Context context, OnTimeSetListener listener, int hourOfDay,
                            int minute, boolean is24HourView) { super(context); throw new RuntimeException("Stub!"); }
    public void updateTime(int hourOfDay, int minuteOfHour) STUB
    public interface OnTimeSetListener {
        void onTimeSet(TimePicker view, int hourOfDay, int minute);
    }
}
'''
src = src.rstrip("\n") + "\n" + ADDITIONS.lstrip("\n")
open(spec_path, "w").write(src)
print("patched -> %d lines" % len(src.splitlines()))
