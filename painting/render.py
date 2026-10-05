import sys, time, numpy as np
sys.path.insert(0, '/home/user/Claude/painting')
import engine, scene, compose
S = float(sys.argv[1]) if len(sys.argv) > 1 else 0.5
out = sys.argv[2] if len(sys.argv) > 2 else '/tmp/claude-0/-home-user-Claude/3f029ca9-7aae-503a-a1e7-010003867119/scratchpad/scene.png'
scene.S = S
W, H = int(round(scene.W0 * S)), int(round(scene.H0 * S))
rng = np.random.default_rng(3)
t = time.time()
img, parts = compose.build(W, H, rng)
engine.save(img, out)
print('scene', W, H, round(time.time() - t, 1), 's')
