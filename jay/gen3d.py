#!/usr/bin/env python3
"""gen3d.py out.png "prompt" [ref.png ...] [--ar 9:16] -- Gemini image gen in the jay.vs.life 3D style."""
import os, sys, importlib.util
HERE = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location("g", os.path.join(HERE, "..", "cartoon", "gen_img.py"))
g = importlib.util.module_from_spec(spec); spec.loader.exec_module(g)
g.STYLE = ("Cute stylized 3D render, soft clay / vinyl-toy look like a modern animated short film: smooth rounded shapes, "
           "big round head, large expressive eyes with highlights, small nose, very readable exaggerated facial expression, "
           "soft studio lighting with gentle shadows, warm pastel color palette (peach, mint, lilac, butter yellow), "
           "simple tidy cozy environment, vertical composition with the characters in the middle and empty space in the "
           "top third, no text, no letters, no logos, no watermark.")
if __name__ == "__main__":
    a = sys.argv[1:]; ar = "9:16"
    if "--ar" in a: i = a.index("--ar"); ar = a[i + 1]; del a[i:i + 2]
    print(g.gen(a[0], a[1], a[2:], ar))
