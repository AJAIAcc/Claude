public class Sync {
    private int count;
    private static long total;
    synchronized void inc(int by) { count += by; }
    synchronized int risky(int x) {
        if (x < 0) throw new IllegalArgumentException("neg " + x);
        try { return 100 / x; } catch (ArithmeticException e) { return -1; }
    }
    static synchronized long addTotal(long v) { total += v; return total; }
    synchronized double mixed(long a, double b, int c) {
        synchronized (this) { return a * b + c; }
    }
    public static void main(String[] args) {
        Sync s = new Sync();
        for (int i = 0; i < 5; i++) s.inc(i);
        System.out.println(s.count);
        System.out.println(s.risky(5) + " " + s.risky(0));
        try { s.risky(-3); } catch (IllegalArgumentException e) { System.out.println("caught " + e.getMessage()); }
        System.out.println(addTotal(5) + addTotal(7));
        System.out.println(s.mixed(3L, 1.5, 2));
        Object lock = new Object();
        int r = 0;
        for (int i = 0; i < 3; i++) {
            synchronized (lock) {
                try { if (i == 1) throw new RuntimeException("x"); r += 10; }
                catch (RuntimeException e) { r += 1; }
            }
        }
        System.out.println(r);
    }
}
