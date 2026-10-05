import sys, time, numpy as np
sys.path.insert(0, '/home/user/Claude/painting')
import engine, scene, compose, paint as painter
S = float(sys.argv[1]) if len(sys.argv) > 1 else 0.5
out = sys.argv[2] if len(sys.argv) > 2 else '/tmp/claude-0/-home-user-Claude/3f029ca9-7aae-503a-a1e7-010003867119/scratchpad/paint.png'
scene.S = S
W, H = int(round(scene.W0 * S)), int(round(scene.H0 * S))
rng = np.random.default_rng(3)
t = time.time()
target, parts = compose.build(W, H, rng)
print('underpainting', round(time.time()-t,1)); t = time.time()
cv, aux = painter.paint(target, parts, W, H, rng)
print('brushwork', round(time.time()-t,1)); t=time.time()
final = painter.finish(cv, target, aux, parts, W, H, rng)
print('finishing', round(time.time()-t,1))
engine.save(final, out)
engine.save(cv.rgb, out.replace('.png','_raw.png'))
engine.save(target, out.replace('.png','_under.png'))
np.save('/tmp/claude-0/-home-user-Claude/3f029ca9-7aae-503a-a1e7-010003867119/scratchpad/hgt.npy', cv.hgt)
print('done', W, H)
