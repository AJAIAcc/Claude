"""Add service, VPN and package-manager APIs to spec_content.txt (idempotent)."""
import os

here = os.path.dirname(os.path.abspath(__file__))
spec_path = os.path.join(here, "spec_content.txt")
src = open(spec_path).read()

if "android/net/VpnService.java" in src:
    print("already patched")
    raise SystemExit(0)

# ---- 1. Context: package manager + service control -------------------------
old = "    public final String getString(int resId) STUB\n}"
new = ("    public final String getString(int resId) STUB\n"
       "    public abstract android.content.pm.PackageManager getPackageManager();\n"
       "    public abstract android.content.ComponentName startService(Intent service);\n"
       "    public abstract boolean stopService(Intent service);\n"
       "}")
assert src.count(old) == 1, "Context anchor"
src = src.replace(old, new)

# ---- 2. ContextWrapper: concrete overrides ---------------------------------
old = "    public java.io.File getCacheDir() STUB\n}"
new = ("    public java.io.File getCacheDir() STUB\n"
       "    public android.content.pm.PackageManager getPackageManager() STUB\n"
       "    public android.content.ComponentName startService(Intent service) STUB\n"
       "    public boolean stopService(Intent service) STUB\n"
       "}")
assert src.count(old) == 1, "ContextWrapper anchor"
src = src.replace(old, new)

# ---- 3. Activity: startActivityForResult / onActivityResult ----------------
old = "    public void startActivity(Intent intent) STUB\n    public final void runOnUiThread(Runnable action) STUB"
new = ("    public void startActivity(Intent intent) STUB\n"
       "    public void startActivityForResult(Intent intent, int requestCode) STUB\n"
       "    protected void onActivityResult(int requestCode, int resultCode, Intent data) STUB\n"
       "    public final void runOnUiThread(Runnable action) STUB")
assert src.count(old) == 1, "Activity anchor"
src = src.replace(old, new)

# ---- 4. New classes --------------------------------------------------------
ADDITIONS = r'''
//// android/content/ComponentName.java
package android.content;
public final class ComponentName {
    public ComponentName(String pkg, String cls) STUB
    public String getPackageName() STUB
    public String getClassName() STUB
    public String flattenToString() STUB
}
//// android/os/IBinder.java
package android.os;
public interface IBinder {
}
//// android/os/ParcelFileDescriptor.java
package android.os;
public class ParcelFileDescriptor implements java.io.Closeable {
    ParcelFileDescriptor() STUB
    public java.io.FileDescriptor getFileDescriptor() STUB
    public int getFd() STUB
    public int detachFd() STUB
    public long getStatSize() STUB
    public void close() throws java.io.IOException STUB
}
//// android/content/pm/ApplicationInfo.java
package android.content.pm;
public class ApplicationInfo {
    public static final int FLAG_SYSTEM = 0x00000001;
    public static final int FLAG_DEBUGGABLE = 0x00000002;
    public static final int FLAG_HAS_CODE = 0x00000004;
    public static final int FLAG_PERSISTENT = 0x00000008;
    public static final int FLAG_ALLOW_CLEAR_USER_DATA = 0x00000040;
    public static final int FLAG_UPDATED_SYSTEM_APP = 0x00000080;
    public static final int FLAG_TEST_ONLY = 0x00000100;
    public static final int FLAG_ALLOW_BACKUP = 0x00008000;
    public static final int FLAG_STOPPED = 0x00200000;
    public String packageName;
    public String name;
    public String sourceDir;
    public String dataDir;
    public int flags;
    public int uid;
    public int targetSdkVersion;
    public boolean enabled;
    public ApplicationInfo() STUB
}
//// android/content/pm/PackageInfo.java
package android.content.pm;
public class PackageInfo {
    public static final int REQUESTED_PERMISSION_GRANTED = 0x00000002;
    public String packageName;
    public String versionName;
    public int versionCode;
    public long firstInstallTime;
    public long lastUpdateTime;
    public String[] requestedPermissions;
    public int[] requestedPermissionsFlags;
    public ApplicationInfo applicationInfo;
    public PackageInfo() STUB
}
//// android/content/pm/PackageManager.java
package android.content.pm;
import android.content.Intent;
public abstract class PackageManager {
    public static final int GET_META_DATA = 0x00000080;
    public static final int GET_PERMISSIONS = 0x00001000;
    public static final int MATCH_UNINSTALLED_PACKAGES = 0x00002000;
    public static final int MATCH_DISABLED_COMPONENTS = 0x00000200;
    public static final int PERMISSION_GRANTED = 0;
    public static final int PERMISSION_DENIED = -1;
    public PackageManager() STUB
    public abstract java.util.List<ApplicationInfo> getInstalledApplications(int flags);
    public abstract java.util.List<PackageInfo> getInstalledPackages(int flags);
    public abstract PackageInfo getPackageInfo(String packageName, int flags) throws NameNotFoundException;
    public abstract ApplicationInfo getApplicationInfo(String packageName, int flags) throws NameNotFoundException;
    public abstract CharSequence getApplicationLabel(ApplicationInfo info);
    public abstract String getInstallerPackageName(String packageName);
    public abstract Intent getLaunchIntentForPackage(String packageName);
    public abstract int checkPermission(String permName, String pkgName);
    public static class NameNotFoundException extends Exception {
        public NameNotFoundException() STUB
        public NameNotFoundException(String name) STUB
    }
}
//// android/app/Service.java
package android.app;
import android.content.Intent;
import android.os.IBinder;
public abstract class Service extends android.content.ContextWrapper {
    public static final int START_STICKY_COMPATIBILITY = 0;
    public static final int START_STICKY = 1;
    public static final int START_NOT_STICKY = 2;
    public static final int START_REDELIVER_INTENT = 3;
    public Service() { super(null); throw new RuntimeException("Stub!"); }
    public void onCreate() STUB
    public int onStartCommand(Intent intent, int flags, int startId) STUB
    public void onDestroy() STUB
    public abstract IBinder onBind(Intent intent);
    public final void stopSelf() STUB
    public void stopSelf(int startId) STUB
}
//// android/net/VpnService.java
package android.net;
import android.content.Context;
import android.content.Intent;
import android.content.pm.PackageManager;
import android.os.IBinder;
import android.os.ParcelFileDescriptor;
public class VpnService extends android.app.Service {
    public static final String SERVICE_INTERFACE = "android.net.VpnService";
    public VpnService() STUB
    public static Intent prepare(Context context) STUB
    public boolean protect(int socket) STUB
    public void onRevoke() STUB
    public IBinder onBind(Intent intent) STUB
    public class Builder {
        public Builder() STUB
        public Builder addAddress(String address, int prefixLength) STUB
        public Builder addRoute(String address, int prefixLength) STUB
        public Builder addDnsServer(String address) STUB
        public Builder addSearchDomain(String domain) STUB
        public Builder addAllowedApplication(String packageName) throws PackageManager.NameNotFoundException STUB
        public Builder addDisallowedApplication(String packageName) throws PackageManager.NameNotFoundException STUB
        public Builder setSession(String session) STUB
        public Builder setMtu(int mtu) STUB
        public Builder setBlocking(boolean blocking) STUB
        public Builder allowFamily(int family) STUB
        public ParcelFileDescriptor establish() STUB
    }
}
//// android/provider/Settings.java
package android.provider;
public final class Settings {
    public static final String ACTION_APPLICATION_DETAILS_SETTINGS = "android.settings.APPLICATION_DETAILS_SETTINGS";
    public static final String ACTION_SETTINGS = "android.settings.SETTINGS";
    public static final String ACTION_VPN_SETTINGS = "android.net.vpn.SETTINGS";
    private Settings() {}
}
'''

src = src.rstrip("\n") + "\n" + ADDITIONS.lstrip("\n")
open(spec_path, "w").write(src)
print("patched spec_content.txt -> %d lines" % len(src.splitlines()))
