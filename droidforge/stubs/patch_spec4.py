"""Fourth stub pass: scheduled jobs, notifications, APK archive inspection."""
import os

here = os.path.dirname(os.path.abspath(__file__))
spec_path = os.path.join(here, "spec_content.txt")
src = open(spec_path).read()

if "android/app/job/JobService.java" in src:
    print("already patched")
    raise SystemExit(0)

# --- Context: more services, permission self-check ---------------------------
old = '    public static final String KEYGUARD_SERVICE = "keyguard";'
new = ('    public static final String KEYGUARD_SERVICE = "keyguard";\n'
       '    public static final String NOTIFICATION_SERVICE = "notification";\n'
       '    public static final String JOB_SCHEDULER_SERVICE = "jobscheduler";')
assert src.count(old) == 1, "Context services anchor"
src = src.replace(old, new)

old = "    public abstract ContentResolver getContentResolver();"
new = ("    public abstract ContentResolver getContentResolver();\n"
       "    public abstract int checkSelfPermission(String permission);")
assert src.count(old) == 1, "Context checkSelfPermission anchor"
src = src.replace(old, new)

old = "    public ContentResolver getContentResolver() STUB"
new = ("    public ContentResolver getContentResolver() STUB\n"
       "    public int checkSelfPermission(String permission) STUB")
assert src.count(old) == 1, "ContextWrapper anchor"
src = src.replace(old, new)

# --- Activity: runtime permission request ------------------------------------
old = "    protected void onActivityResult(int requestCode, int resultCode, Intent data) STUB"
new = ("    protected void onActivityResult(int requestCode, int resultCode, Intent data) STUB\n"
       "    public final void requestPermissions(String[] permissions, int requestCode) STUB\n"
       "    public void onRequestPermissionsResult(int requestCode, String[] permissions,\n"
       "                                          int[] grantResults) STUB\n"
       "    public boolean shouldShowRequestPermissionRationale(String permission) STUB")
assert src.count(old) == 1, "Activity anchor"
src = src.replace(old, new)

# --- Intent: document picking -------------------------------------------------
old = '    public static final String ACTION_SEND = "android.intent.action.SEND";'
new = ('    public static final String ACTION_SEND = "android.intent.action.SEND";\n'
       '    public static final String ACTION_OPEN_DOCUMENT = "android.intent.action.OPEN_DOCUMENT";\n'
       '    public static final String ACTION_GET_CONTENT = "android.intent.action.GET_CONTENT";\n'
       '    public static final String CATEGORY_OPENABLE = "android.intent.category.OPENABLE";')
assert src.count(old) == 1, "Intent constants anchor"
src = src.replace(old, new)

old = "    public Intent setType(String type) STUB"
new = ("    public Intent setType(String type) STUB\n"
       "    public Intent addCategory(String category) STUB\n"
       "    public android.net.Uri getData() STUB\n"
       "    public Intent setData(android.net.Uri data) STUB")
assert src.count(old) == 1, "Intent methods anchor"
src = src.replace(old, new)

# --- PackageManager: read an APK file without installing it -------------------
old = "    public static final int GET_SIGNING_CERTIFICATES = 0x08000000;"
new = ("    public static final int GET_SIGNING_CERTIFICATES = 0x08000000;\n"
       "    public static final int GET_SERVICES = 0x00000004;\n"
       "    public static final int GET_RECEIVERS = 0x00000002;")
assert src.count(old) == 1, "PackageManager constants anchor"
src = src.replace(old, new)

old = "    public abstract java.util.List<ResolveInfo> queryIntentServices(Intent intent, int flags);"
new = ("    public abstract java.util.List<ResolveInfo> queryIntentServices(Intent intent, int flags);\n"
       "    public abstract PackageInfo getPackageArchiveInfo(String archiveFilePath, int flags);")
assert src.count(old) == 1, "PackageManager archive anchor"
src = src.replace(old, new)

# --- PackageInfo: declared components ----------------------------------------
old = "    public SigningInfo signingInfo;"
new = ("    public SigningInfo signingInfo;\n"
       "    public ServiceInfo[] services;\n"
       "    public ActivityInfo[] receivers;")
assert src.count(old) == 1, "PackageInfo anchor"
src = src.replace(old, new)

# --- ContentResolver: read the picked document -------------------------------
old = '''//// android/content/ContentResolver.java
package android.content;
public class ContentResolver {
    ContentResolver() STUB
}'''
new = '''//// android/content/ContentResolver.java
package android.content;
public class ContentResolver {
    ContentResolver() STUB
    public java.io.InputStream openInputStream(android.net.Uri uri) throws java.io.FileNotFoundException STUB
    public String getType(android.net.Uri uri) STUB
}'''
assert src.count(old) == 1, "ContentResolver anchor"
src = src.replace(old, new)

ADDITIONS = r'''
//// android/app/PendingIntent.java
package android.app;
import android.content.Context;
import android.content.Intent;
public final class PendingIntent {
    public static final int FLAG_ONE_SHOT = 0x40000000;
    public static final int FLAG_NO_CREATE = 0x20000000;
    public static final int FLAG_CANCEL_CURRENT = 0x10000000;
    public static final int FLAG_UPDATE_CURRENT = 0x08000000;
    public static final int FLAG_IMMUTABLE = 0x04000000;
    public static final int FLAG_MUTABLE = 0x02000000;
    PendingIntent() STUB
    public static PendingIntent getActivity(Context context, int requestCode, Intent intent, int flags) STUB
    public static PendingIntent getBroadcast(Context context, int requestCode, Intent intent, int flags) STUB
    public static PendingIntent getService(Context context, int requestCode, Intent intent, int flags) STUB
    public void cancel() STUB
}
//// android/app/Notification.java
package android.app;
import android.content.Context;
public class Notification {
    public static final int PRIORITY_DEFAULT = 0;
    public static final int PRIORITY_HIGH = 1;
    public Notification() STUB
    public static class Builder {
        public Builder(Context context, String channelId) STUB
        public Builder setContentTitle(CharSequence title) STUB
        public Builder setContentText(CharSequence text) STUB
        public Builder setSmallIcon(int icon) STUB
        public Builder setAutoCancel(boolean autoCancel) STUB
        public Builder setOngoing(boolean ongoing) STUB
        public Builder setOnlyAlertOnce(boolean onlyAlertOnce) STUB
        public Builder setContentIntent(PendingIntent intent) STUB
        public Builder setWhen(long when) STUB
        public Builder setShowWhen(boolean show) STUB
        public Builder setStyle(Style style) STUB
        public Notification build() STUB
    }
    public static abstract class Style {
        public Style() STUB
    }
    public static class BigTextStyle extends Style {
        public BigTextStyle() STUB
        public BigTextStyle bigText(CharSequence text) STUB
    }
}
//// android/app/NotificationChannel.java
package android.app;
public final class NotificationChannel {
    public NotificationChannel(String id, CharSequence name, int importance) STUB
    public void setDescription(String description) STUB
    public void setShowBadge(boolean showBadge) STUB
    public String getId() STUB
}
//// android/app/NotificationManager.java
package android.app;
public class NotificationManager {
    public static final int IMPORTANCE_NONE = 0;
    public static final int IMPORTANCE_MIN = 1;
    public static final int IMPORTANCE_LOW = 2;
    public static final int IMPORTANCE_DEFAULT = 3;
    public static final int IMPORTANCE_HIGH = 4;
    NotificationManager() STUB
    public void createNotificationChannel(NotificationChannel channel) STUB
    public void notify(int id, Notification notification) STUB
    public void cancel(int id) STUB
    public void cancelAll() STUB
    public boolean areNotificationsEnabled() STUB
}
//// android/app/job/JobParameters.java
package android.app.job;
public class JobParameters {
    JobParameters() STUB
    public int getJobId() STUB
}
//// android/app/job/JobInfo.java
package android.app.job;
import android.content.ComponentName;
public class JobInfo {
    public static final int NETWORK_TYPE_NONE = 0;
    public static final int NETWORK_TYPE_ANY = 1;
    public static final int NETWORK_TYPE_UNMETERED = 2;
    JobInfo() STUB
    public int getId() STUB
    public static final class Builder {
        public Builder(int jobId, ComponentName jobService) STUB
        public Builder setPeriodic(long intervalMillis) STUB
        public Builder setPersisted(boolean isPersisted) STUB
        public Builder setRequiredNetworkType(int networkType) STUB
        public Builder setRequiresCharging(boolean requiresCharging) STUB
        public Builder setRequiresDeviceIdle(boolean requiresDeviceIdle) STUB
        public JobInfo build() STUB
    }
}
//// android/app/job/JobScheduler.java
package android.app.job;
public abstract class JobScheduler {
    public static final int RESULT_FAILURE = 0;
    public static final int RESULT_SUCCESS = 1;
    public JobScheduler() STUB
    public abstract int schedule(JobInfo job);
    public abstract void cancel(int jobId);
    public abstract void cancelAll();
}
//// android/app/job/JobService.java
package android.app.job;
import android.content.Intent;
import android.os.IBinder;
public abstract class JobService extends android.app.Service {
    public JobService() STUB
    public final IBinder onBind(Intent intent) STUB
    public abstract boolean onStartJob(JobParameters params);
    public abstract boolean onStopJob(JobParameters params);
    public final void jobFinished(JobParameters params, boolean wantsReschedule) STUB
}
'''

src = src.rstrip("\n") + "\n" + ADDITIONS.lstrip("\n")
open(spec_path, "w").write(src)
print("patched -> %d lines" % len(src.splitlines()))
