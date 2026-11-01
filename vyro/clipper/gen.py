import json,os,sys,base64,urllib.request
K=[l.split("=",1)[1].strip().strip('"') for l in open(os.path.expanduser("~/.config/shorts/env")) if "GEMINI_API_KEY" in l][0]
name,prompt=sys.argv[1],sys.argv[2]
body={"contents":[{"parts":[{"text":prompt}]}]}
r=urllib.request.Request(f"https://generativelanguage.googleapis.com/v1beta/models/lyria-3.5:generateContent?key={K}",json.dumps(body).encode(),{"Content-Type":"application/json"})
try: j=json.loads(urllib.request.urlopen(r,timeout=600).read())
except urllib.error.HTTPError as e: print(e.code,e.read()[:500]); sys.exit(1)
for p in j["candidates"][0]["content"]["parts"]:
    if "inlineData" in p:
        ext={"audio/mpeg":"mp3","audio/wav":"wav"}.get(p["inlineData"]["mimeType"],"bin")
        open(f"{name}.{ext}","wb").write(base64.b64decode(p["inlineData"]["data"])); print("saved",name,ext,p["inlineData"]["mimeType"])
    elif "text" in p: print("text:",p["text"][:200])
