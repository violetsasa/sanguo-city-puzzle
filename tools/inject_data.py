"""把 out/cities_final.json 寫回 ../index.html 的 STATES 與 ADJ_PAIRS 區塊（不動成就與其他程式）。
用法：python inject_data.py [輸出檔路徑]    （不給路徑就直接改 ../index.html）"""
import json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
src = os.path.join(HERE, "..", "index.html")
dst = sys.argv[1] if len(sys.argv) > 1 else src
d = json.load(open(os.path.join(HERE, "out", "cities_final.json"), encoding="utf-8"))
s = open(src, encoding="utf-8").read()

def flat(pts):
    return ";".join("%g,%g" % (x, y) for x, y in pts)

a = s.index("//  三國名城")
b = s.index("const COL=")
lines = ["//  三國名城：以西元 240 年前後為準，挑選有明確歸屬、在三國史上有分量的地點（取自《三國群英傳 M》的地圖清單）；每座城放在歷史位置，依「離哪座城最近」切出範圍（Voronoi），再與漢地範圍的現代地級市界線相交 [經度，緯度]；z=漢末所屬的州，f=三國鼎立時的勢力",
         "// 隔海的夷州（臺灣）、邪馬台（北九州）、大和（畿內）與交趾（越南北部）：參考原版把離島挪到鄰近陸地旁的做法，輪廓平移到緊貼大陸海岸／國界（輪廓取自 Natural Earth，公有領域）",
         "const STATES=["]
for u in d["units"]:
    lines.append(" {n:'%s',f:'%s',z:'%s',l:[%g,%g],r:%g,v:'%s',p:'%s'}," % (u["n"], u["f"], u["z"], u["l"][0], u["l"][1], u["r"], flat(u["v"]), flat(u["p"])))
lines.append("];")
lines.append('// v=繪圖用精細輪廓、p=物理用簡化輪廓（以 "經度，緯度；..." 儲存）')
lines.append('STATES.forEach(s=>{const f=t=>t.split(";").map(q=>q.split(",").map(Number));s.v=f(s.v);s.p=f(s.p);});')
lines.append('const ADJ_PAIRS="%s".split(" ");' % " ".join(d["adj"]))
lines.append("const adj=new Set(ADJ_PAIRS.flatMap(t=>{const [x,y]=t.split('|');return [x+'|'+y,y+'|'+x];}));")
lines.append("const isAdj=(a,b)=>adj.has(a.n+'|'+b.n);")
s = s[:a] + "\n".join(lines) + "\n" + s[b:]
open(dst, "w", encoding="utf-8", newline="").write(s)
print("寫入", dst, "共", len(d["units"]), "座城")
