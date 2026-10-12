public class Arrays2 {
    static long sum(long[] a) { long s = 0; for (long v : a) s += v; return s; }
    static void fill(double[] d, double v) { for (int i = 0; i < d.length; i++) d[i] = v * i; }
    public static void main(String[] args) {
        byte[] b = new byte[4]; b[0] = (byte) 250; b[1] = 100; b[1] += 100;
        short[] s = {1, 2, (short) 40000};
        char[] c = new char[3]; c[0] = 'H'; c[1] = 'i'; c[2] = (char) (c[1] + 1);
        boolean[] z = new boolean[2]; z[1] = !z[0];
        int[] ia = {5, 4, 3, 2, 1};
        long[] la = {1L << 33, -1, 7};
        float[] fa = {1.5f, 2.25f};
        double[] da = new double[4];
        fill(da, 1.5);
        String[] sa = {"x", null, "z"};
        Object[] oa = new Object[]{1, "two", 3.0, 'c', true, null};
        System.out.println(b[0] + " " + b[1] + " " + s[2] + " " + String.valueOf(c) + " " + z[0] + z[1]);
        System.out.println(sum(la) + " " + (fa[0] + fa[1]) + " " + da[3] + " " + sa[1] + sa[2] + " " + oa.length);
        for (Object o : oa) System.out.print(o + ",");
        System.out.println();
        int[][] m = new int[3][];
        for (int i = 0; i < 3; i++) { m[i] = new int[i + 1]; for (int j = 0; j <= i; j++) m[i][j] = i * j; }
        System.out.println(m[2][2] + " " + m[1].length);
        long[][][] cube = new long[2][3][4];
        cube[1][2][3] = 99;
        System.out.println(cube[1][2][3] + cube[0][0][0] + " " + cube[1].length + cube[1][2].length);
        String[][] grid = new String[2][2];
        grid[0][1] = "g";
        System.out.println(grid[0][1] + grid[1][0]);
        int[] copy = ia.clone();
        copy[0] = 100;
        System.arraycopy(ia, 1, copy, 2, 3);
        StringBuilder sb = new StringBuilder();
        for (int v : copy) sb.append(v).append(' ');
        System.out.println(sb + "| " + ia[0]);
        char[] rev = "hello".toCharArray();
        for (int i = 0, j = rev.length - 1; i < j; i++, j--) { char t = rev[i]; rev[i] = rev[j]; rev[j] = t; }
        System.out.println(rev);
        int[] counts = new int[26];
        for (char ch : "the quick brown fox".toCharArray()) if (ch != ' ') counts[ch - 'a']++;
        System.out.println(counts['o' - 'a'] + " " + counts['q' - 'a']);
        boolean[][] bg = new boolean[2][2]; bg[1][1] = true;
        System.out.println(bg[1][1] && !bg[0][0]);
    }
}
