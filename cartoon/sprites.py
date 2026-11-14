#!/usr/bin/env python3
"""sprites.py sheet.png outdir name1 name2 ... -- chroma-key a green pose sheet and save each pose (reading order) as a trimmed RGBA PNG."""
import sys, os
import numpy as np
from PIL import Image
from scipy import ndimage
def key(rgb):
    r, g, b = [rgb[..., i].astype(np.float32) for i in range(3)]
    gdom = g - np.maximum(r, b)
    a = np.clip(1 - (gdom - 40) / 60, 0, 1)          # soft edge
    out = rgb.astype(np.float32).copy()
    spill = np.clip(g - np.maximum(r, b), 0, None)    # despill
    out[..., 1] -= spill * (a < 1) * 0.9
    return np.dstack([np.clip(out, 0, 255), a * 255]).astype(np.uint8)
def main(sheet, outdir, names):
    rgba = key(np.array(Image.open(sheet).convert("RGB")))
    m = rgba[..., 3] > 128
    m = ndimage.binary_closing(m, iterations=6)
    lab, n = ndimage.label(m)
    objs = [(sl, (lab[sl] == i + 1).sum()) for i, sl in enumerate(ndimage.find_objects(lab))]
    objs = [o for o in objs if o[1] > m.size * 0.004]
    rows = sorted(objs, key=lambda o: o[0][0].start)
    # group into rows by vertical centre, then sort by x
    H = m.shape[0]; objs = sorted(objs, key=lambda o: (round(((o[0][0].start + o[0][0].stop) / 2) / (H / 2.2)), o[0][1].start))
    os.makedirs(outdir, exist_ok=True)
    for (sl, _), nm in zip(objs, names):
        y0, y1, x0, x1 = sl[0].start, sl[0].stop, sl[1].start, sl[1].stop
        Image.fromarray(rgba[max(0, y0 - 4):y1 + 4, max(0, x0 - 4):x1 + 4]).save(os.path.join(outdir, nm + ".png"))
    print(len(objs), "sprites")
if __name__ == "__main__": main(sys.argv[1], sys.argv[2], sys.argv[3:])
