"""Eighth stub pass: media decoding (MediaExtractor/MediaCodec), cursors, document display names."""
import os
here = os.path.dirname(os.path.abspath(__file__))
spec_path = os.path.join(here, "spec_content.txt")
src = open(spec_path).read()
if "android/media/MediaCodec.java" in src:
    print("already patched")
    raise SystemExit(0)

old = "    public Intent setData(android.net.Uri data) STUB"
new = (old + "\n"
       "    public Intent setDataAndType(android.net.Uri data, String type) STUB\n"
       "    public Intent putExtra(String name, String[] value) STUB")
assert src.count(old) == 1, "Intent anchor"
src = src.replace(old, new)
old = "    public static final int FLAG_ACTIVITY_NEW_TASK = 0x10000000;"
new = (old + "\n"
       "    public static final int FLAG_GRANT_READ_URI_PERMISSION = 0x00000001;\n"
       "    public static final String EXTRA_MIME_TYPES = \"android.intent.extra.MIME_TYPES\";")
assert src.count(old) == 1, "Intent flag anchor"
src = src.replace(old, new)

old = "    public String getType(android.net.Uri uri) STUB"
new = (old + "\n"
       "    public final android.database.Cursor query(android.net.Uri uri, String[] projection, String selection, String[] selectionArgs, String sortOrder) STUB")
assert src.count(old) == 1, "ContentResolver anchor"
src = src.replace(old, new)

src = src.rstrip("\n") + "\n" + r'''//// android/database/Cursor.java
package android.database;
public interface Cursor extends java.io.Closeable {
    boolean moveToFirst();
    int getColumnIndex(String columnName);
    String getString(int columnIndex);
    long getLong(int columnIndex);
    boolean isNull(int columnIndex);
    void close();
}
//// android/provider/OpenableColumns.java
package android.provider;
public interface OpenableColumns {
    String DISPLAY_NAME = "_display_name";
    String SIZE = "_size";
}
//// android/view/Surface.java
package android.view;
public class Surface {
    Surface() STUB
}
//// android/media/MediaCrypto.java
package android.media;
public final class MediaCrypto {
    MediaCrypto() STUB
}
//// android/media/MediaFormat.java
package android.media;
public final class MediaFormat {
    public static final String KEY_MIME = "mime";
    public static final String KEY_SAMPLE_RATE = "sample-rate";
    public static final String KEY_CHANNEL_COUNT = "channel-count";
    public static final String KEY_DURATION = "durationUs";
    public static final String KEY_PCM_ENCODING = "pcm-encoding";
    public MediaFormat() STUB
    public final boolean containsKey(String name) STUB
    public final int getInteger(String name) STUB
    public final long getLong(String name) STUB
    public final String getString(String name) STUB
    public final void setInteger(String name, int value) STUB
}
//// android/media/MediaExtractor.java
package android.media;
public final class MediaExtractor {
    public MediaExtractor() STUB
    public final void setDataSource(android.content.Context context, android.net.Uri uri, java.util.Map<String, String> headers) throws java.io.IOException STUB
    public final void setDataSource(java.io.FileDescriptor fd) throws java.io.IOException STUB
    public final int getTrackCount() STUB
    public MediaFormat getTrackFormat(int index) STUB
    public void selectTrack(int index) STUB
    public int readSampleData(java.nio.ByteBuffer byteBuf, int offset) STUB
    public long getSampleTime() STUB
    public int getSampleFlags() STUB
    public boolean advance() STUB
    public final void release() STUB
}
//// android/media/MediaCodec.java
package android.media;
public final class MediaCodec {
    public static final int BUFFER_FLAG_END_OF_STREAM = 4;
    public static final int INFO_TRY_AGAIN_LATER = -1;
    public static final int INFO_OUTPUT_FORMAT_CHANGED = -2;
    public static final int INFO_OUTPUT_BUFFERS_CHANGED = -3;
    public static final class BufferInfo {
        public int flags;
        public int offset;
        public long presentationTimeUs;
        public int size;
        public BufferInfo() STUB
    }
    MediaCodec() STUB
    public static MediaCodec createDecoderByType(String type) throws java.io.IOException STUB
    public void configure(MediaFormat format, android.view.Surface surface, MediaCrypto crypto, int flags) STUB
    public final void start() STUB
    public final void stop() STUB
    public final void release() STUB
    public final int dequeueInputBuffer(long timeoutUs) STUB
    public java.nio.ByteBuffer getInputBuffer(int index) STUB
    public final void queueInputBuffer(int index, int offset, int size, long presentationTimeUs, int flags) STUB
    public final int dequeueOutputBuffer(BufferInfo info, long timeoutUs) STUB
    public java.nio.ByteBuffer getOutputBuffer(int index) STUB
    public final MediaFormat getOutputFormat() STUB
    public final void releaseOutputBuffer(int index, boolean render) STUB
}
'''
open(spec_path, "w").write(src)
print("patched")
