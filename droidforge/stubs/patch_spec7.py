"""Seventh stub pass: broadcast receivers."""
import os
here = os.path.dirname(os.path.abspath(__file__))
spec_path = os.path.join(here, "spec_content.txt")
src = open(spec_path).read()
if "android/content/BroadcastReceiver.java" in src:
    print("already patched")
    raise SystemExit(0)

old = "    public abstract int checkSelfPermission(String permission);"
new = (old + "\n"
       "    public abstract Intent registerReceiver(BroadcastReceiver receiver, IntentFilter filter);\n"
       "    public abstract void unregisterReceiver(BroadcastReceiver receiver);\n"
       "    public abstract void sendBroadcast(Intent intent);")
assert src.count(old) == 1, "Context anchor"
src = src.replace(old, new)

old = "    public int checkSelfPermission(String permission) STUB"
new = (old + "\n"
       "    public Intent registerReceiver(BroadcastReceiver receiver, IntentFilter filter) STUB\n"
       "    public void unregisterReceiver(BroadcastReceiver receiver) STUB\n"
       "    public void sendBroadcast(Intent intent) STUB")
assert src.count(old) == 1, "ContextWrapper anchor"
src = src.replace(old, new)

old = "    public static Uri parse(String uriString) STUB"
new = (old + "\n"
       "    public abstract String getScheme();\n"
       "    public abstract String getSchemeSpecificPart();\n"
       "    public abstract String getEncodedSchemeSpecificPart();\n"
       "    public abstract String getHost();\n"
       "    public abstract String getPath();")
assert src.count(old) == 1, "Uri anchor"
src = src.replace(old, new)

old = '    public static final String ACTION_VIEW = "android.intent.action.VIEW";'
new = (old + "\n"
       '    public static final String ACTION_PACKAGE_ADDED = "android.intent.action.PACKAGE_ADDED";\n'
       '    public static final String ACTION_PACKAGE_REPLACED = "android.intent.action.PACKAGE_REPLACED";\n'
       '    public static final String ACTION_PACKAGE_REMOVED = "android.intent.action.PACKAGE_REMOVED";\n'
       '    public static final String ACTION_PACKAGE_FULLY_REMOVED = "android.intent.action.PACKAGE_FULLY_REMOVED";\n'
       '    public static final String ACTION_BOOT_COMPLETED = "android.intent.action.BOOT_COMPLETED";\n'
       '    public static final String EXTRA_REPLACING = "android.intent.extra.REPLACING";')
assert src.count(old) == 1, "Intent actions anchor"
src = src.replace(old, new)

ADDITIONS = r'''
//// android/content/IntentFilter.java
package android.content;
public class IntentFilter {
    public IntentFilter() STUB
    public IntentFilter(String action) STUB
    public IntentFilter(String action, String dataType) STUB
    public final void addAction(String action) STUB
    public final void addCategory(String category) STUB
    public final void addDataScheme(String scheme) STUB
    public final void setPriority(int priority) STUB
    public final int countActions() STUB
}
//// android/content/BroadcastReceiver.java
package android.content;
public abstract class BroadcastReceiver {
    public BroadcastReceiver() STUB
    public abstract void onReceive(Context context, Intent intent);
    public final PendingResult goAsync() STUB
    public final void setResultCode(int code) STUB
    public static class PendingResult {
        PendingResult() STUB
        public final void finish() STUB
    }
}
'''
src = src.rstrip("\n") + "\n" + ADDITIONS.lstrip("\n")
open(spec_path, "w").write(src)
print("patched -> %d lines" % len(src.splitlines()))
