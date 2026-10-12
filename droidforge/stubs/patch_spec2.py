"""Second stub pass: DNS forwarding and per-app attribution. Idempotent."""
import os

here = os.path.dirname(os.path.abspath(__file__))
spec_path = os.path.join(here, "spec_content.txt")
src = open(spec_path).read()

if "android/net/ConnectivityManager.java" in src:
    print("already patched")
    raise SystemExit(0)

# Context: CONNECTIVITY_SERVICE constant
old = '    public static final String AUDIO_SERVICE = "audio";'
new = ('    public static final String AUDIO_SERVICE = "audio";\n'
       '    public static final String CONNECTIVITY_SERVICE = "connectivity";')
assert src.count(old) == 1, "Context service constants anchor"
src = src.replace(old, new)

# PackageManager: uid -> packages
old = "    public abstract int checkPermission(String permName, String pkgName);"
new = ("    public abstract int checkPermission(String permName, String pkgName);\n"
       "    public abstract String[] getPackagesForUid(int uid);\n"
       "    public abstract String getNameForUid(int uid);")
assert src.count(old) == 1, "PackageManager anchor"
src = src.replace(old, new)

# VpnService: protect a DatagramSocket so our upstream lookups skip the tunnel
old = "    public boolean protect(int socket) STUB"
new = ("    public boolean protect(int socket) STUB\n"
       "    public boolean protect(java.net.Socket socket) STUB\n"
       "    public boolean protect(java.net.DatagramSocket socket) STUB")
assert src.count(old) == 1, "VpnService protect anchor"
src = src.replace(old, new)

ADDITIONS = r'''
//// android/net/ConnectivityManager.java
package android.net;
public class ConnectivityManager {
    ConnectivityManager() STUB
    public int getConnectionOwnerUid(int protocol, java.net.InetSocketAddress local,
                                     java.net.InetSocketAddress remote) STUB
}
//// android/os/Process.java
package android.os;
public class Process {
    public static final int INVALID_UID = -1;
    public Process() STUB
    public static final int myUid() STUB
    public static final int myPid() STUB
}
'''

src = src.rstrip("\n") + "\n" + ADDITIONS.lstrip("\n")
open(spec_path, "w").write(src)
print("patched -> %d lines" % len(src.splitlines()))
