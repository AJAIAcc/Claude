import java.util.ArrayList;
import java.util.List;

interface Shape { double area(); default String label() { return "shape"; } }
abstract class Base implements Shape {
    protected String name;
    static int created = 0;
    Base(String name) { this.name = name; created++; }
    public abstract double area();
    public String toString() { return name + "[" + area() + "]"; }
    String describe() { return "Base:" + name; }
}
class Circle extends Base {
    double r;
    Circle(double r) { super("circle"); this.r = r; }
    public double area() { return 3.0 * r * r; }
    String describe() { return "Circle/" + super.describe(); }
}
class Rect extends Base {
    final int w, h;
    Rect(int w, int h) { super("rect"); this.w = w; this.h = h; }
    public double area() { return w * h; }
}
class Square extends Rect {
    Square(int s) { super(s, s); name = "square"; }
    @Override String describe() { return "Square!"; }
}
enum Color { RED, GREEN, BLUE; Color next() { return values()[(ordinal() + 1) % values().length]; } }
class MyException extends RuntimeException {
    int code;
    MyException(String m, int code) { super(m); this.code = code; }
}
public class OOP {
    int counter;
    class Inner { int bump() { return ++counter; } }
    static class Node { int val; Node next; Node(int v, Node n) { val = v; next = n; } }
    static int sumList(Node n) { int s = 0; while (n != null) { s += n.val; n = n.next; } return s; }
    static String colorName(Color c) {
        switch (c) { case RED: return "r"; case GREEN: return "g"; default: return "b"; }
    }
    static int thrower(int x) {
        try {
            if (x == 1) throw new MyException("one", 11);
            if (x == 2) throw new IllegalStateException("two");
            if (x == 3) return 1 / (x - 3);
            return x * 2;
        } catch (MyException e) {
            return e.code + e.getMessage().length();
        } catch (IllegalStateException | ArithmeticException e) {
            return -1;
        } finally {
            System.out.print("[f" + x + "]");
        }
    }
    public static void main(String[] args) {
        List<Shape> shapes = new ArrayList<>();
        shapes.add(new Circle(2));
        shapes.add(new Rect(3, 4));
        shapes.add(new Square(5));
        double total = 0;
        for (Shape s : shapes) { total += s.area(); System.out.println(s + " " + ((Base) s).describe() + " " + s.label()); }
        System.out.println("total=" + total + " created=" + Base.created);
        OOP o = new OOP();
        OOP.Inner in1 = o.new Inner();
        in1.bump(); in1.bump();
        System.out.println(o.counter);
        Node list = new Node(1, new Node(2, new Node(3, null)));
        System.out.println(sumList(list));
        Color c = Color.RED;
        for (int i = 0; i < 4; i++) { System.out.print(c + ":" + c.ordinal() + ":" + colorName(c) + " "); c = c.next(); }
        System.out.println(Color.valueOf("BLUE").name());
        for (int i = 0; i < 5; i++) System.out.print(thrower(i) + " ");
        System.out.println();
        try {
            Object x = "hello";
            Integer bad = (Integer) x;
            System.out.println(bad);
        } catch (ClassCastException e) { System.out.println("cce"); }
        try {
            int[] arr = new int[2];
            arr[5] = 1;
        } catch (ArrayIndexOutOfBoundsException e) { System.out.println("aioobe"); }
        try {
            try { throw new MyException("inner", 1); }
            finally { System.out.println("inner finally"); }
        } catch (RuntimeException e) { System.out.println("outer caught " + e.getMessage()); }
        Runnable r = new Runnable() { public void run() { System.out.println("anon run " + Base.created); } };
        r.run();
        Object lock = new Object();
        synchronized (lock) { System.out.println("in sync"); }
        StringBuilder sb = new StringBuilder("ab");
        sb.append(1).append('c').append(2.5).append(true).append(3L).append(1.5f).append((Object) null);
        System.out.println(sb.toString() + sb.length());
        Integer i1 = 127; int i2 = i1 + 1; Long l1 = 5L; Double d1 = 2.5;
        System.out.println(i2 + " " + (l1 * 2) + " " + (d1 / 2) + " " + i1.equals(127) + " " + "x".equals("x"));
    }
}
