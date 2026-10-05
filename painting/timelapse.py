"""Render the painting and film it being painted."""
import os, sys, time, subprocess
import numpy as np
sys.path.insert(0, '/home/user/Claude/painting')
import engine, scene, compose
import paint as painter

S = float(sys.argv[1]) if len(sys.argv) > 1 else 0.5
out = sys.argv[2] if len(sys.argv) > 2 else '/home/user/Claude/out/perseus_andromeda.png'
frames = sys.argv[3] if len(sys.argv) > 3 else '/tmp/claude-0/-home-user-Claude/3f029ca9-7aae-503a-a1e7-010003867119/scratchpad/frames'
mp4 = out.replace('.png', '_timelapse.mp4')

scene.S = S
W, H = int(round(scene.W0 * S)), int(round(scene.H0 * S))
rng = np.random.default_rng(3)

t = time.time()
target, parts = compose.build(W, H, rng)
print('underpainting %.0fs' % (time.time() - t)); t = time.time()

snap = painter.Snapper(frames, width=900, stride=1)
cv, aux = painter.paint(target, parts, W, H, rng, snap=snap)
print('brushwork %.0fs, %d frames' % (time.time() - t, snap.n)); t = time.time()
final = painter.finish(cv, target, aux, parts, W, H, rng, snap=snap)
print('finishing %.0fs, %d frames total' % (time.time() - t, snap.n))

engine.save(final, out)
engine.save(target, out.replace('.png', '_under.png'))

# 25 fps, a little slower at the start so the lay-in reads
subprocess.run(['ffmpeg', '-y', '-loglevel', 'error', '-framerate', '25',
                '-i', os.path.join(frames, 'f%05d.png'),
                '-c:v', 'libx264', '-pix_fmt', 'yuv420p', '-crf', '18',
                '-vf', 'scale=trunc(iw/2)*2:trunc(ih/2)*2', mp4], check=True)
print('wrote', mp4, '%.1f s of film' % (snap.n / 25.0))
