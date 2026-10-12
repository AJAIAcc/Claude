public class Control {
    static String kind(int v) {
        switch (v) {
            case 0: return "zero";
            case 1: case 2: return "small";
            case 100: return "hundred";
            case -5: return "neg5";
            case 99999: return "big";
            default: return "other";
        }
    }
    static int dense(int v) {
        switch (v) { case 3: return 30; case 4: return 40; case 5: return 50; case 6: return 60; case 7: return 70; default: return -1; }
    }
    static String word(String s) {
        switch (s) {
            case "apple": return "fruit";
            case "carrot": return "veg";
            case "Aa": return "Aa";
            case "BB": return "BB";   // same hashCode as "Aa"
            default: return "?";
        }
    }
    public static void main(String[] args) {
        StringBuilder sb = new StringBuilder();
        for (int v : new int[]{0, 1, 2, 100, -5, 99999, 7}) sb.append(kind(v)).append(',');
        System.out.println(sb);
        for (int v = 2; v < 9; v++) System.out.print(dense(v) + " ");
        System.out.println();
        System.out.println(word("apple") + word("carrot") + word("Aa") + word("BB") + word("x"));
        outer:
        for (int i = 0; i < 5; i++) {
            for (int j = 0; j < 5; j++) {
                if (j == 3) continue outer;
                if (i == 3) break outer;
                System.out.print(i * 10 + j + " ");
            }
        }
        System.out.println();
        int n = 0;
        do { n += 3; } while (n < 20);
        int w = 100;
        while (w > 1) w = (w % 2 == 0) ? w / 2 : 3 * w + 1;
        System.out.println(n + " " + w);
        boolean t = true, f = false;
        System.out.println((t && !f) + " " + (t & f) + " " + (t | f) + " " + (t ^ t) + " " + (f || (n > 5)));
        Object o = "str";
        String r = o instanceof String ? "is string" : "not";
        Integer boxed = 42;
        Object ob = boxed;
        System.out.println(r + " " + (ob instanceof Integer) + " " + (ob instanceof String) + " " + (null instanceof Object));
        int total = 0;
        for (int i = 0; i < 1000; i++) { if (i % 7 == 0) continue; total += i; if (total > 100000) break; }
        System.out.println(total);
        long acc = 1;
        for (long L = 1; L <= 20; L++) acc *= L;
        System.out.println(acc);
        char[] cs = {'d', 'a', 'c', 'b'};
        for (int i = 0; i < cs.length; i++) for (int j = 0; j < cs.length - 1 - i; j++)
            if (cs[j] > cs[j + 1]) { char tmp = cs[j]; cs[j] = cs[j + 1]; cs[j + 1] = tmp; }
        System.out.println(cs);
        System.out.println(String.valueOf(cs) + cs.length);
    }
}
