package dev.aj.hermes;

import android.content.Context;

import java.io.File;
import java.io.FileInputStream;
import java.io.FileOutputStream;
import java.io.IOException;
import java.io.InputStream;
import java.io.OutputStream;
import java.util.ArrayList;
import java.util.List;

/**
 * Conversations on disk, as one JSON file in the app's private storage.
 *
 * Writes go to a temporary file which then replaces the real one, so a crash
 * or a kill mid-write loses the newest turn rather than the whole history —
 * the previous file is intact until the rename completes.
 */
final class Store {

    private static final String NAME = "conversations.json";
    /** Enough that a long chat survives; small enough not to bloat the app's data. */
    private static final int MAX_CONVERSATIONS = 200;

    private final File file;
    private final File temp;

    Store(Context c) {
        File dir = c.getFilesDir();
        file = new File(dir, NAME);
        temp = new File(dir, NAME + ".tmp");
    }

    /** Everything on disk, newest first. Never throws. */
    List<Chat.Conversation> load() {
        String text = null;
        try {
            if (file.exists()) {
                text = read(file);
            } else if (temp.exists()) {
                // A write was interrupted before the rename; the temp file is
                // the newer of the two, so prefer it over nothing.
                text = read(temp);
            }
        } catch (IOException e) {
            text = null;
        }
        List<Chat.Conversation> all = Chat.load(text);
        Chat.sort(all);
        return all;
    }

    /**
     * Replaces the stored copy. Returns false if it could not be written, so
     * the caller can tell the user rather than silently losing their chat.
     */
    boolean save(List<Chat.Conversation> all) {
        List<Chat.Conversation> keep = all;
        if (all.size() > MAX_CONVERSATIONS) {
            Chat.sort(all);
            keep = new ArrayList<Chat.Conversation>(all.subList(0, MAX_CONVERSATIONS));
        }
        try {
            write(temp, Chat.save(keep));
            // renameTo won't overwrite on every filesystem, so clear the way.
            if (file.exists() && !file.delete()) {
                // Fall back to writing in place: worse, but better than not saving.
                write(file, Chat.save(keep));
                temp.delete();
                return true;
            }
            if (!temp.renameTo(file)) {
                write(file, Chat.save(keep));
                temp.delete();
            }
            return true;
        } catch (IOException e) {
            return false;
        }
    }

    private static String read(File f) throws IOException {
        InputStream in = new FileInputStream(f);
        try {
            byte[] buf = new byte[8192];
            java.io.ByteArrayOutputStream out = new java.io.ByteArrayOutputStream();
            int n;
            while ((n = in.read(buf)) > 0) {
                out.write(buf, 0, n);
            }
            return new String(out.toByteArray(), "UTF-8");
        } finally {
            close(in);
        }
    }

    private static void write(File f, String text) throws IOException {
        OutputStream out = new FileOutputStream(f);
        try {
            out.write(text.getBytes("UTF-8"));
            out.flush();
        } finally {
            close(out);
        }
    }

    private static void close(java.io.Closeable c) {
        try {
            c.close();
        } catch (IOException ignored) {
            // nothing useful to do on close
        }
    }
}
