#!/usr/bin/env python3
"""gen3d.py out.png "prompt" [ref.png ...] [--ar 9:16] -- Gemini image gen in the jay.vs.life "egg-head" 3D style."""
import os, sys, importlib.util
HERE = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location("g", os.path.join(HERE, "..", "cartoon", "gen_img.py"))
g = importlib.util.module_from_spec(spec); spec.loader.exec_module(g)
g.STYLE = ("Polished high-end 3D animated-film render with absurd proportions: characters have an enormous smooth egg-shaped "
           "head about as big as their whole body, a tiny body with short stubby arms and legs, very small simple black dot eyes, "
           "thin straight eyebrows, a tiny mouth and no visible nose, glossy soft materials. Expressions are dead-pan and subtle, "
           "conveyed mostly by the eyebrows. Detailed cozy realistic-looking room, cinematic soft lighting, saturated but tasteful "
           "warm colors, vertical composition, no text, no letters, no logos, no watermark.")
if __name__ == "__main__":
    a = sys.argv[1:]; ar = "9:16"
    if "--ar" in a: i = a.index("--ar"); ar = a[i + 1]; del a[i:i + 2]
    print(g.gen(a[0], a[1], a[2:], ar))
