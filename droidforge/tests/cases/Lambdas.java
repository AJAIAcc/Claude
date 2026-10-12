import java.util.ArrayList;
import java.util.List;

public class Lambdas {
    interface IntOp { int apply(int a, int b); }
    interface Fn<A, B> { B apply(A a); }
    interface LongSup { long get(); }
    interface Consumer3 { void accept(String s, long l, double d); }
    int base = 100;
    private int priv(int x) { return x + base; }
    private static String stat(String s) { return s + "!"; }
    static int twice(int x) { return x * 2; }
    int instanceSum(List<Integer> xs) {
        int[] acc = {0};
        Fn<Integer, Integer> f = v -> v + base;
        for (Integer x : xs) acc[0] += f.apply(x);
        return acc[0];
    }
    public static void main(String[] args) {
        IntOp add = (a, b) -> a + b;
        IntOp mul = (a, b) -> a * b;
        int k = 7;
        IntOp capt = (a, b) -> a * k - b;
        System.out.println(add.apply(2, 3) + " " + mul.apply(4, 5) + " " + capt.apply(3, 1));
        Fn<String, String> ex = Lambdas::stat;
        Fn<Integer, Integer> tw = Lambdas::twice;
        Fn<String, Integer> len = String::length;
        Fn<Integer, String> tos = x -> "v" + x;
        System.out.println(ex.apply("hi") + " " + tw.apply(21) + " " + len.apply("abcd") + " " + tos.apply(9));
        Lambdas l = new Lambdas();
        Fn<Integer, Integer> p = l::priv;
        System.out.println(p.apply(5));
        List<Integer> xs = new ArrayList<>();
        for (int i = 1; i <= 4; i++) xs.add(i);
        System.out.println(l.instanceSum(xs));
        long big = 1L << 40;
        LongSup ls = () -> big + k;
        System.out.println(ls.get());
        double dd = 1.5;
        Consumer3 c3 = (s, lo, d) -> System.out.println(s + lo + d + dd + k);
        c3.accept("s", 9L, 0.25);
        Fn<String, StringBuilder> mk = StringBuilder::new;
        System.out.println(mk.apply("built").append("!"));
        Runnable[] rs = new Runnable[3];
        for (int i = 0; i < 3; i++) { final int j = i; rs[i] = () -> System.out.print("r" + j + " "); }
        for (Runnable r : rs) r.run();
        System.out.println();
        Fn<Fn<Integer, Integer>, Integer> hof = fn -> fn.apply(10) + 1;
        System.out.println(hof.apply(x -> x * x));
    }
}
