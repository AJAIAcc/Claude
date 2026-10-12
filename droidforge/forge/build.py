"""droidforge build pipeline:  Java sources -> signed, installable APK.

    python3 -m forge build <project-dir>        build project (see app.json)
    python3 -m forge new <project-dir> <package> "<App Name>"   scaffold a project
    python3 -m forge check <file.apk>           verify an APK built by this tool
"""
import glob
import json
import os
import shutil
import subprocess
import sys
import tempfile

from . import apk as A
from . import resc as RC
from . import resources as R
from .classfile import ClassFile
from .dexcheck import DexFile
from .dexwriter import DexWriter
from .translate import TranslateError, translate_classes

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
STUBS_JAR = os.path.join(ROOT, "stubs", "android-stubs.jar")
DEFAULT_KEYDIR = os.path.join(ROOT, "keystore")


class BuildError(Exception):
    pass


def log(msg):
    print("[forge] " + msg, flush=True)


def parse_color(s):
    s = s.lstrip("#")
    if len(s) == 6:
        s = "FF" + s
    v = int(s, 16)
    return v, ((v >> 16) & 255, (v >> 8) & 255, v & 255)


def javac(srcs, out, classpath):
    env = dict(os.environ)
    env.pop("JAVA_TOOL_OPTIONS", None)
    cmd = ["javac", "-Xlint:-options", "-encoding", "UTF-8", "--release", "8", "-g",
           "-cp", classpath, "-d", out] + srcs
    r = subprocess.run(cmd, capture_output=True, text=True, env=env)
    if r.returncode != 0:
        raise BuildError("javac failed:\n" + r.stderr)
    if r.stderr.strip():
        print(r.stderr)


def build(project, out_apk=None, keydir=None):
    cfg_path = os.path.join(project, "app.json")
    cfg = json.load(open(cfg_path))
    pkg = cfg["package"]
    name = cfg.get("name", pkg.split(".")[-1])
    activity = cfg.get("activity", "MainActivity")
    if "." not in activity:
        activity = pkg + "." + activity
    min_sdk = int(cfg.get("min_sdk", 24))
    target_sdk = int(cfg.get("target_sdk", 34))
    if min_sdk < 24:
        raise BuildError("min_sdk must be >= 24 (this toolchain signs with APK Signature Scheme v2 only)")
    out_apk = out_apk or os.path.join(project, "build", "%s-%s.apk" % (name.replace(" ", ""),
                                                                      cfg.get("version_name", "1.0")))
    work = tempfile.mkdtemp(prefix="forge-")
    try:
        # 1. resources first: the generated R class has to exist before javac runs
        icon = cfg.get("icon", {})
        bg_argb, bg_rgb = parse_color(icon.get("background", "#3F51B5"))
        _, fg_rgb = parse_color(icon.get("foreground", "#FFFFFF"))
        letter = icon.get("letter", name[:1] or "A")
        custom_png = icon.get("png")
        if custom_png:
            legacy_png = open(os.path.join(project, custom_png), "rb").read()
        else:
            legacy_png = R.make_icon(192, bg_rgb, fg_rgb, letter)
        fg_png = R.make_foreground(432, fg_rgb, letter)
        p_legacy = "res/mipmap-xxxhdpi-v4/ic_launcher.png"
        p_fg = "res/mipmap-xxxhdpi-v4/ic_launcher_foreground.png"
        p_adaptive = "res/mipmap-anydpi-v26/ic_launcher.xml"

        entries = [("color", "ic_launcher_background", "color", bg_argb, (0, 0)),
                   ("mipmap", "ic_launcher", "file", p_legacy, (R.DENSITY_XXXHDPI, 4))]
        if not custom_png:
            entries.append(("mipmap", "ic_launcher", "file", p_adaptive, (R.DENSITY_ANY, 26)))
            entries.append(("mipmap", "ic_launcher_foreground", "file", p_fg,
                            (R.DENSITY_XXXHDPI, 4)))

        res_dir = os.path.join(project, "res")
        try:
            scanned, xml_paths, binaries = RC.scan(res_dir)
        except RC.ResError as e:
            raise BuildError("res/: %s" % e)
        entries.extend(scanned)
        if scanned:
            log("res: %d resource(s) from res/" % len(scanned))
        try:
            arsc, ids = RC.build_table(pkg, 0x7F, entries)
        except RC.ResError as e:
            raise BuildError("res/: %s" % e)
        resolve = RC.make_resolver(ids)

        files = [(p_legacy, legacy_png, True)]
        if not custom_png:
            adaptive = R.adaptive_icon_xml(ids[("color", "ic_launcher_background")],
                                           ids[("mipmap", "ic_launcher_foreground")])
            files += [(p_fg, fg_png, True), (p_adaptive, adaptive, False)]
        for apk_path in sorted(binaries):
            files.append((apk_path, binaries[apk_path], True))
        for apk_path in sorted(xml_paths):
            try:
                files.append((apk_path, RC.compile_xml(xml_paths[apk_path], resolve), False))
            except RC.ResError as e:
                raise BuildError("res/: %s" % e)

        gen_dir = os.path.join(work, "gen")
        os.makedirs(os.path.join(gen_dir, *pkg.split(".")), exist_ok=True)
        r_path = os.path.join(gen_dir, *(pkg.split(".") + ["R.java"]))
        r_source = RC.generate_r(pkg, ids)
        open(r_path, "w").write(r_source)
        # Keep a copy beside the APK: real Android keeps its generated R too, and
        # it is what makes the resource ids inspectable after the fact.
        try:
            keep_dir = os.path.join(project, "build", "gen")
            os.makedirs(keep_dir, exist_ok=True)
            open(os.path.join(keep_dir, "R.java"), "w").write(r_source)
        except Exception:
            pass
        log("res: generated R with %d id(s)" % len(ids))

        # 2. compile
        srcs = sorted(glob.glob(os.path.join(project, "src", "**", "*.java"), recursive=True))
        if not srcs:
            raise BuildError("no Java sources under %s/src" % project)
        srcs = srcs + [r_path]
        cls_dir = os.path.join(work, "classes")
        os.makedirs(cls_dir)
        libs = sorted(glob.glob(os.path.join(project, "libs", "*.jar")))
        log("javac: %d source file(s)" % len(srcs))
        javac(srcs, cls_dir, os.pathsep.join([STUBS_JAR] + libs))
        class_files = sorted(glob.glob(os.path.join(cls_dir, "**", "*.class"), recursive=True))
        # classes from bundled plain-Java libraries (jars) are dexed too
        for jar in libs:
            jd = os.path.join(work, "lib-" + os.path.basename(jar))
            os.makedirs(jd)
            shutil.unpack_archive(jar, jd, "zip")
            class_files += [f for f in glob.glob(os.path.join(jd, "**", "*.class"), recursive=True)
                            if not f.endswith("module-info.class")]

        # 2. dex
        cfs = [ClassFile(open(f, "rb").read()) for f in class_files]
        for cf in cfs:
            if cf.name.startswith("android/"):
                raise BuildError("class %s is in the android.* namespace" % cf.name)
        log("dex: translating %d classes" % len(cfs))
        try:
            dclasses = translate_classes(cfs)
        except TranslateError as e:
            raise BuildError("dex translation failed: %s" % e)
        dex = DexWriter(dclasses, min_sdk=min_sdk).write()
        chk = DexFile(dex)
        if chk.errors:
            raise BuildError("dex validation failed:\n  " + "\n  ".join(chk.errors[:30]))
        acts = {("L%s;" % activity.replace(".", "/"))}
        if not any(c.desc in acts for c in dclasses):
            raise BuildError("activity class %s not found in sources" % activity)
        have = {c.desc for c in dclasses}
        for _kind in ("services", "receivers"):
            for _s in cfg.get(_kind, []):
                _n = _s if isinstance(_s, str) else _s["name"]
                _n = _n if "." in _n else pkg + "." + _n
                if ("L%s;" % _n.replace(".", "/")) not in have:
                    raise BuildError("%s class %s declared in app.json but not found in sources"
                                     % (_kind[:-1], _n))
        log("dex: %d bytes, %d classes, %d methods, verified OK" % (len(dex), len(chk.classes), len(chk.methods)))

        # 4. manifest
        extra = [a if "." in a else pkg + "." + a for a in cfg.get("activities", [])]
        orient = {None: None, "portrait": 1, "landscape": 0, "sensorPortrait": 7,
                  "sensorLandscape": 6}[cfg.get("orientation")]
        def qualify(spec):
            spec = {"name": spec} if isinstance(spec, str) else dict(spec)
            if "." not in spec["name"]:
                spec["name"] = pkg + "." + spec["name"]
            for md in spec.get("meta_data", ()):
                if isinstance(md.get("resource"), str):
                    md["resource"] = resolve(md["resource"])
            return spec

        svcs = [qualify(s) for s in cfg.get("services", [])]
        rcvs = [qualify(r) for r in cfg.get("receivers", [])]
        app_md = []
        for md in cfg.get("meta_data", []):
            md = dict(md)
            if isinstance(md.get("resource"), str):
                md["resource"] = resolve(md["resource"])
            app_md.append(md)
        label = name
        if cfg.get("label_res"):
            label = ("ref", resolve(cfg["label_res"]))
        man = R.manifest(pkg, int(cfg.get("version_code", 1)), str(cfg.get("version_name", "1.0")),
                         label, activity, min_sdk=min_sdk, target_sdk=target_sdk,
                         icon_ref=ids[("mipmap", "ic_launcher")],
                         extra_activities=extra, permissions=cfg.get("permissions", []),
                         orientation=orient, services=svcs, receivers=rcvs,
                         app_meta_data=app_md,
                         allow_backup=cfg.get("allow_backup", True))

        # 5. zip
        entries = [("AndroidManifest.xml", man, False, 1),
                   ("classes.dex", dex, False, 1),
                   ("resources.arsc", arsc, True, 4)]
        for (p, data, store) in files:
            entries.append((p, data, store, 4))
        assets_dir = os.path.join(project, "assets")
        if os.path.isdir(assets_dir):
            for f in sorted(glob.glob(os.path.join(assets_dir, "**", "*"), recursive=True)):
                if os.path.isfile(f):
                    rel = os.path.relpath(f, project).replace(os.sep, "/")
                    entries.append((rel, open(f, "rb").read(), False, 1))
        unsigned = A.build_zip(entries)

        # 6. sign + verify
        key, cert = A.load_or_create_key(keydir or DEFAULT_KEYDIR)
        signed = A.sign_v2(unsigned, key, cert)
        rep = A.verify_v2(signed)
        os.makedirs(os.path.dirname(os.path.abspath(out_apk)), exist_ok=True)
        open(out_apk, "wb").write(signed)
        log("signed (v2, %s) cert sha256 %s..." % (rep["cert"], rep["cert_sha256"][:16]))
        log("APK: %s (%d bytes)" % (out_apk, len(signed)))
        return out_apk
    finally:
        shutil.rmtree(work, ignore_errors=True)


TEMPLATE = r'''package %(pkg)s;

import android.app.Activity;
import android.graphics.Color;
import android.os.Bundle;
import android.view.Gravity;
import android.widget.Button;
import android.widget.LinearLayout;
import android.widget.TextView;

public class MainActivity extends Activity {
    private int taps = 0;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        LinearLayout root = new LinearLayout(this);
        root.setOrientation(LinearLayout.VERTICAL);
        root.setGravity(Gravity.CENTER);
        root.setBackgroundColor(Color.WHITE);

        final TextView label = new TextView(this);
        label.setText("Hello from %(name)s!");
        label.setTextSize(28);
        label.setTextColor(Color.BLACK);
        label.setGravity(Gravity.CENTER);
        root.addView(label);

        Button button = new Button(this);
        button.setText("Tap me");
        button.setOnClickListener(v -> label.setText("Tapped " + (++taps) + " times"));
        root.addView(button);

        setContentView(root);
    }
}
'''


def new_project(path, pkg, name):
    os.makedirs(os.path.join(path, "src", *pkg.split(".")), exist_ok=True)
    json.dump({"package": pkg, "name": name, "version_code": 1, "version_name": "1.0",
               "activity": "MainActivity", "min_sdk": 24, "target_sdk": 34,
               "icon": {"background": "#3F51B5", "foreground": "#FFFFFF", "letter": name[:1]}},
              open(os.path.join(path, "app.json"), "w"), indent=2)
    open(os.path.join(path, "src", *pkg.split("."), "MainActivity.java"), "w").write(
        TEMPLATE % {"pkg": pkg, "name": name})
    log("created project in " + path)


def main(argv):
    if len(argv) >= 2 and argv[0] == "build":
        out = None
        if "-o" in argv:
            out = argv[argv.index("-o") + 1]
        try:
            build(argv[1], out)
        except BuildError as e:
            print("BUILD FAILED: %s" % e, file=sys.stderr)
            sys.exit(1)
    elif len(argv) >= 4 and argv[0] == "new":
        new_project(argv[1], argv[2], argv[3])
    elif len(argv) >= 2 and argv[0] == "check":
        data = open(argv[1], "rb").read()
        print(A.verify_v2(data))
    else:
        print(__doc__)
        sys.exit(2)
