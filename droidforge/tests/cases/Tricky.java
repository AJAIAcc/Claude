import java.util.ArrayList;
import java.util.List;

interface Greeter {
    String greet(String n);
    static Greeter polite() { return n -> "Dear " + n; }
    default Greeter twice() { return n -> greet(greet(n)); }
}

public class Tricky {
    private int secret = 41;
    private static String hidden() { return "hidden"; }
    static int initOrder = 0;
    static final int[] TABLE;
    static { TABLE = new int[4]; for (int i = 0; i < 4; i++) TABLE[i] = i * i; initOrder = 7; }
    int field1 = 3;
    { field1 += 10; }
    Tricky() { field1 *= 2; }

    class In { int peek() { return secret + 1; } String h() { return hidden(); } }

    static int finallyReturn(int x) {
        int r = 0;
        try {
            try {
                if (x > 2) return x * 100;
                r = x;
            } finally {
                r += 1000;
                if (x == 5) return -5;
            }
        } finally {
            r += 1;
        }
        return r;
    }
    static int sum(int... xs) { int s = 0; for (int x : xs) s += x; return s; }
    static <T extends Comparable<T>> T max(T a, T b) { return a.compareTo(b) >= 0 ? a : b; }
    static String charKind(char c) {
        switch (c) { case 'a': case 'e': case 'i': case 'o': case 'u': return "V"; case ' ': return "_"; default: return "c"; }
    }
    static long collatz(long n) { long steps = 0; while (n != 1) { n = (n & 1) == 0 ? n >> 1 : 3 * n + 1; steps++; } return steps; }
    static double mix(int i, long l, float f, double d) { return i + l * f - d / i; }
    static String nested(int a, int b) {
        String s = "";
        for (int i = 0; i < a; i++) {
            for (int j = 0; j < b; j++) {
                s += (i == j) ? "D" : (i < j ? "u" : "l");
            }
            s += "|";
        }
        return s;
    }
    public static void main(String[] args) {
        Tricky t = new Tricky();
        System.out.println(initOrder + " " + TABLE[3] + " " + t.field1);
        Tricky.In in = t.new In();
        System.out.println(in.peek() + in.h());
        for (int x = 0; x < 7; x++) System.out.print(finallyReturn(x) + " ");
        System.out.println();
        System.out.println(sum() + " " + sum(1) + " " + sum(1, 2, 3, 4));
        System.out.println(max("pear", "apple") + max(3, 9));
        StringBuilder sb = new StringBuilder();
        for (char c : "hi you".toCharArray()) sb.append(charKind(c));
        System.out.println(sb);
        System.out.println(collatz(27) + " " + collatz(837799));
        System.out.println(mix(3, 1L << 35, 0.5f, 7.25));
        System.out.println(nested(3, 4));
        Greeter g = Greeter.polite();
        System.out.println(g.greet("Ann") + " / " + g.twice().greet("Bo"));
        List<String> names = new ArrayList<>();
        names.add("x"); names.add("yy"); names.add("zzz");
        int total = 0;
        for (String n : names) total += n.length();
        System.out.println(total + " " + names.get(2) + names.size());
        long big = Long.MAX_VALUE;
        int ov = Integer.MAX_VALUE;
        System.out.println((big + 1) + " " + (ov * 2) + " " + (ov + ov + 2) + " " + (long) ov * 2 + " " + Long.MIN_VALUE / -1);
        int a = 5, b = 0;
        boolean safe = b != 0 && a / b > 1;
        System.out.println(safe + " " + (b == 0 || a / b > 1));
        Object[] objs = {1, 2L, 3.0f, 4.0, "5", '6', (short) 7, (byte) 8, true};
        for (Object o : objs) System.out.print(o + (o instanceof Number ? "n " : "o "));
        System.out.println();
        int[] fib = new int[20];
        fib[0] = 0; fib[1] = 1;
        for (int i = 2; i < fib.length; i++) fib[i] = fib[i - 1] + fib[i - 2];
        System.out.println(fib[19]);
        String s = null;
        System.out.println("null concat: " + s + " " + (s == null));
        char c = 'A';
        c += 2;
        c++;
        int ci = c + 1;
        System.out.println(c + " " + ci + " " + (char) ci + " " + (c > 'B'));
        float fl = 16777216f;
        System.out.println((fl + 1f) + " " + (0.1f + 0.2f) + " " + (float) 1e-10 + " " + 3.4e38f * 10);
    }
}
