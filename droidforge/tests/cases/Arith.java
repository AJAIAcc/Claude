public class Arith {
    static int si(int a, int b) { return a / b; }
    public static void main(String[] args) {
        int a = Integer.MAX_VALUE, b = -7, c = 3;
        System.out.println(a + 1);
        System.out.println(b / c + " " + b % c + " " + (b >> 1) + " " + (b >>> 28) + " " + (b << 3));
        System.out.println((a & 0xff) + " " + (a | 256) + " " + (a ^ b) + " " + (~b) + " " + (-b));
        long x = Long.MIN_VALUE, y = 1234567890123L;
        System.out.println(x - 1);
        System.out.println(y * y + " " + y / 7 + " " + y % 7 + " " + (y >> 5) + " " + (x >>> 60) + " " + (y << 40));
        System.out.println((y & 0xffffL) + " " + (y | 1L) + " " + (y ^ x) + " " + (~y) + " " + (-y));
        float f = 1.1f, g = 3.0f;
        System.out.println(f * g + " " + f / g + " " + f % g + " " + (f - g) + " " + (-f));
        double d = 0.1, e = 0.2;
        System.out.println(d + e);
        System.out.println(d * 1e10 + " " + d / 3 + " " + 1e-5 + " " + 123456789.0 + " " + 1e7 + " " + 12345.678);
        System.out.println((int) 3.99 + " " + (int) -3.99 + " " + (long) 1e19 + " " + (int) Float.NaN + " " + (int) 1e20);
        System.out.println((char) 65 + " " + (byte) 200 + " " + (short) 70000 + " " + (int) 'z' + " " + (char)('a' + 2));
        System.out.println((float) y + " " + (double) f + " " + (long) f + " " + (float) d + " " + (y + 0.5f));
        System.out.println(1.0 / 0 + " " + -1.0 / 0 + " " + 0.0 / 0 + " " + 5 % 3.5 + " " + -0.0);
        System.out.println((d < e) + " " + (d > e) + " " + (f == 1.1f) + " " + (Double.NaN == Double.NaN) + " " + (y > x));
        int i = 10; i += 5; i -= 2; i *= 3; i /= 2; i %= 7; i <<= 3; i >>= 1; i ^= 0x55; i |= 0x100; i &= 0x1f3;
        System.out.println(i);
        long L = 5; L += i; L *= 1000000L; L <<= 3;
        System.out.println(L);
        int k = 0; k++; ++k; k--; k += 1000; k += 100000;
        System.out.println(k);
        short sh = 10; sh += 5; byte by = 127; by++; char ch = 'x'; ch++;
        System.out.println(sh + " " + by + " " + ch);
        try { System.out.println(si(1, 0)); } catch (ArithmeticException ex) { System.out.println("div0 " + ex.getMessage()); }
        System.out.println(Math.max(3, 9) + " " + Math.abs(-4.5) + " " + Math.sqrt(2.0) + " " + Math.round(2.5) + " " + Math.round(-2.5));
        double big = 1.0; for (int n = 0; n < 30; n++) big *= 3.7;
        System.out.println(big);
        float ff = 0.1f; for (int n = 0; n < 10; n++) ff += 0.1f;
        System.out.println(ff);
    }
}
