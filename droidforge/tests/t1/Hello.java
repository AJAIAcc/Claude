public class Hello {
    static int counter = 5;
    static final String NAME = "forge";
    static final long BIG = 1234567890123L;
    int x;
    long y;
    Hello(int x) { this.x = x; this.y = x * 2L; }
    int add(int a) { return x + a; }
    static int fib(int n) { return n < 2 ? n : fib(n - 1) + fib(n - 2); }
    public static void main(String[] args) {
        Hello h = new Hello(3);
        int s = 0;
        for (int i = 0; i < 10; i++) s += h.add(i);
        long l = h.y * 1000000007L;
        double d = s / 3.0;
        String msg = "sum=" + s + " l=" + l + " d=" + d + " fib=" + fib(15) + " " + NAME + BIG;
        System.out.println(msg);
        int[] arr = new int[5];
        boolean[] flags = new boolean[3];
        flags[1] = true;
        arr[2] = flags[1] ? 7 : 9;
        try {
            Object o = null;
            o.toString();
        } catch (NullPointerException e) {
            System.out.println("caught npe " + arr[2]);
        } finally {
            counter++;
        }
        switch (s) { case 1: s = 2; break; case 2: s = 3; break; case 3: s=4; break; default: s = -1; }
        switch (msg) { case "a": s = 10; break; case "b": s = 11; break; default: s += 100; }
        Runnable r = () -> System.out.println("lambda " + h.x + counter);
        r.run();
        int[][] grid = new int[3][4];
        grid[1][2] = 5;
        System.out.println(s + " " + grid[1][2] + " " + grid.length + grid[0].length);
    }
}
