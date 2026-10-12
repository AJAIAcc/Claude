"""Third stub pass: superpower audit, device posture, package signing. Idempotent."""
import os

here = os.path.dirname(os.path.abspath(__file__))
spec_path = os.path.join(here, "spec_content.txt")
src = open(spec_path).read()

if "android/app/admin/DevicePolicyManager.java" in src:
    print("already patched")
    raise SystemExit(0)

# --- Context: more system services, and the content resolver -----------------
old = '    public static final String CONNECTIVITY_SERVICE = "connectivity";'
new = ('    public static final String CONNECTIVITY_SERVICE = "connectivity";\n'
       '    public static final String ACCESSIBILITY_SERVICE = "accessibility";\n'
       '    public static final String DEVICE_POLICY_SERVICE = "device_policy";\n'
       '    public static final String KEYGUARD_SERVICE = "keyguard";')
assert src.count(old) == 1, "Context constants anchor"
src = src.replace(old, new)

old = "    public abstract android.content.pm.PackageManager getPackageManager();"
new = ("    public abstract android.content.pm.PackageManager getPackageManager();\n"
       "    public abstract ContentResolver getContentResolver();")
assert src.count(old) == 1, "Context getPackageManager anchor"
src = src.replace(old, new)

old = "    public android.content.pm.PackageManager getPackageManager() STUB"
new = ("    public android.content.pm.PackageManager getPackageManager() STUB\n"
       "    public ContentResolver getContentResolver() STUB")
assert src.count(old) == 1, "ContextWrapper anchor"
src = src.replace(old, new)

# --- Build: patch level and build tags --------------------------------------
old = "    public static final String RELEASE = rel();"
new = ("    public static final String RELEASE = rel();\n"
       "        public static final String SECURITY_PATCH = rel();")
assert src.count(old) == 1, "Build.VERSION anchor"
src = src.replace(old, new)

old = '    public static final String BRAND = stub();'
new = ('    public static final String BRAND = stub();\n'
       '    public static final String TAGS = stub();\n'
       '    public static final String FINGERPRINT = stub();')
assert src.count(old) == 1, "Build fields anchor"
src = src.replace(old, new)

# --- PackageManager: signing certs and service queries ----------------------
old = "    public static final int GET_PERMISSIONS = 0x00001000;"
new = ("    public static final int GET_PERMISSIONS = 0x00001000;\n"
       "    public static final int GET_SIGNATURES = 0x00000040;\n"
       "    public static final int GET_SIGNING_CERTIFICATES = 0x08000000;\n"
       "    public static final int MATCH_SYSTEM_ONLY = 0x00100000;")
assert src.count(old) == 1, "PackageManager constants anchor"
src = src.replace(old, new)

old = "    public abstract String[] getPackagesForUid(int uid);"
new = ("    public abstract String[] getPackagesForUid(int uid);\n"
       "    public abstract java.util.List<ResolveInfo> queryIntentServices(Intent intent, int flags);\n"
       "    public abstract java.util.List<ResolveInfo> queryBroadcastReceivers(Intent intent, int flags);")
assert src.count(old) == 1, "PackageManager methods anchor"
src = src.replace(old, new)

# --- PackageInfo: signatures ------------------------------------------------
old = "    public ApplicationInfo applicationInfo;\n    public PackageInfo() STUB"
new = ("    public ApplicationInfo applicationInfo;\n"
       "    public Signature[] signatures;\n"
       "    public SigningInfo signingInfo;\n"
       "    public PackageInfo() STUB")
assert src.count(old) == 1, "PackageInfo anchor"
src = src.replace(old, new)

# --- ComponentName: parse a flattened name ----------------------------------
old = "    public String flattenToString() STUB"
new = ("    public String flattenToString() STUB\n"
       "    public static ComponentName unflattenFromString(String str) STUB")
assert src.count(old) == 1, "ComponentName anchor"
src = src.replace(old, new)

# --- Settings: replace with a version carrying Secure and Global ------------
old_settings = '''//// android/provider/Settings.java
package android.provider;
public final class Settings {
    public static final String ACTION_APPLICATION_DETAILS_SETTINGS = "android.settings.APPLICATION_DETAILS_SETTINGS";
    public static final String ACTION_SETTINGS = "android.settings.SETTINGS";
    public static final String ACTION_VPN_SETTINGS = "android.net.vpn.SETTINGS";
    private Settings() {}
}'''
new_settings = '''//// android/provider/Settings.java
package android.provider;
import android.content.ContentResolver;
public final class Settings {
    public static final String ACTION_APPLICATION_DETAILS_SETTINGS = "android.settings.APPLICATION_DETAILS_SETTINGS";
    public static final String ACTION_SETTINGS = "android.settings.SETTINGS";
    public static final String ACTION_VPN_SETTINGS = "android.net.vpn.SETTINGS";
    public static final String ACTION_ACCESSIBILITY_SETTINGS = "android.settings.ACCESSIBILITY_SETTINGS";
    public static final String ACTION_SECURITY_SETTINGS = "android.settings.SECURITY_SETTINGS";
    public static final String ACTION_NOTIFICATION_LISTENER_SETTINGS = "android.settings.ACTION_NOTIFICATION_LISTENER_SETTINGS";
    public static final String ACTION_APPLICATION_DEVELOPMENT_SETTINGS = "android.settings.APPLICATION_DEVELOPMENT_SETTINGS";
    private Settings() {}
    public static final class Secure {
        public static final String ENABLED_ACCESSIBILITY_SERVICES = "enabled_accessibility_services";
        private Secure() {}
        public static String getString(ContentResolver cr, String name) STUB
        public static int getInt(ContentResolver cr, String name, int def) STUB
    }
    public static final class Global {
        public static final String ADB_ENABLED = "adb_enabled";
        public static final String DEVELOPMENT_SETTINGS_ENABLED = "development_settings_enabled";
        public static final String HTTP_PROXY = "http_proxy";
        private Global() {}
        public static String getString(ContentResolver cr, String name) STUB
        public static int getInt(ContentResolver cr, String name, int def) STUB
    }
}'''
assert src.count(old_settings) == 1, "Settings block anchor"
src = src.replace(old_settings, new_settings)

ADDITIONS = r'''
//// android/content/ContentResolver.java
package android.content;
public class ContentResolver {
    ContentResolver() STUB
}
//// android/content/pm/Signature.java
package android.content.pm;
public class Signature {
    public Signature(byte[] signature) STUB
    public byte[] toByteArray() STUB
    public String toCharsString() STUB
}
//// android/content/pm/SigningInfo.java
package android.content.pm;
public final class SigningInfo {
    SigningInfo() STUB
    public Signature[] getApkContentsSigners() STUB
    public Signature[] getSigningCertificateHistory() STUB
    public boolean hasMultipleSigners() STUB
}
//// android/content/pm/ComponentInfo.java
package android.content.pm;
public class ComponentInfo {
    public String name;
    public String packageName;
    public ApplicationInfo applicationInfo;
    public boolean exported;
    public boolean enabled;
    public ComponentInfo() STUB
}
//// android/content/pm/ServiceInfo.java
package android.content.pm;
public class ServiceInfo extends ComponentInfo {
    public String permission;
    public ServiceInfo() STUB
}
//// android/content/pm/ActivityInfo.java
package android.content.pm;
public class ActivityInfo extends ComponentInfo {
    public String permission;
    public ActivityInfo() STUB
}
//// android/content/pm/ResolveInfo.java
package android.content.pm;
public class ResolveInfo {
    public ServiceInfo serviceInfo;
    public ActivityInfo activityInfo;
    public ResolveInfo() STUB
}
//// android/accessibilityservice/AccessibilityServiceInfo.java
package android.accessibilityservice;
public class AccessibilityServiceInfo {
    public static final int FEEDBACK_ALL_MASK = -1;
    public static final int CAPABILITY_CAN_RETRIEVE_WINDOW_CONTENT = 0x00000001;
    public static final int CAPABILITY_CAN_PERFORM_GESTURES = 0x00000020;
    public AccessibilityServiceInfo() STUB
    public String getId() STUB
    public int getCapabilities() STUB
    public android.content.pm.ResolveInfo getResolveInfo() STUB
}
//// android/view/accessibility/AccessibilityManager.java
package android.view.accessibility;
public final class AccessibilityManager {
    AccessibilityManager() STUB
    public boolean isEnabled() STUB
    public java.util.List<android.accessibilityservice.AccessibilityServiceInfo>
            getEnabledAccessibilityServiceList(int feedbackTypeFlags) STUB
    public java.util.List<android.accessibilityservice.AccessibilityServiceInfo>
            getInstalledAccessibilityServiceList() STUB
}
//// android/app/admin/DevicePolicyManager.java
package android.app.admin;
public class DevicePolicyManager {
    DevicePolicyManager() STUB
    public java.util.List<android.content.ComponentName> getActiveAdmins() STUB
    public boolean isDeviceOwnerApp(String packageName) STUB
    public boolean isAdminActive(android.content.ComponentName admin) STUB
}
//// android/app/KeyguardManager.java
package android.app;
public class KeyguardManager {
    KeyguardManager() STUB
    public boolean isDeviceSecure() STUB
    public boolean isKeyguardSecure() STUB
    public boolean isDeviceLocked() STUB
}
'''

src = src.rstrip("\n") + "\n" + ADDITIONS.lstrip("\n")
open(spec_path, "w").write(src)
print("patched -> %d lines" % len(src.splitlines()))
