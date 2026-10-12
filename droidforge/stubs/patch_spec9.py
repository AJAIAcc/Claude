"""Ninth stub pass: DocumentsContract.deleteDocument, ActivityNotFoundException."""
import os
here = os.path.dirname(os.path.abspath(__file__))
spec_path = os.path.join(here, "spec_content.txt")
src = open(spec_path).read()
if "android/provider/DocumentsContract.java" in src:
    print("already patched")
    raise SystemExit(0)
src = src.rstrip("\n") + "\n" + '''//// android/provider/DocumentsContract.java
package android.provider;
public final class DocumentsContract {
    DocumentsContract() STUB
    public static boolean deleteDocument(android.content.ContentResolver content, android.net.Uri documentUri) throws java.io.FileNotFoundException STUB
}
//// android/content/ActivityNotFoundException.java
package android.content;
public class ActivityNotFoundException extends RuntimeException {
    public ActivityNotFoundException() STUB
    public ActivityNotFoundException(String name) STUB
}
'''
open(spec_path, "w").write(src)
print("patched")
