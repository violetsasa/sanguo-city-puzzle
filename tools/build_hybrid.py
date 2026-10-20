import json, sys, os
import shapely
from shapely.geometry import shape, box, Polygon, MultiPolygon, Point, MultiPoint
from shapely.ops import unary_union, voronoi_diagram
from shapely import affinity
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from units_v2 import U as OLD_UNITS
import importlib.util
# 城池清單沿用 build_voronoi.py 內的 CITIES
spec = importlib.util.spec_from_file_location("bv_cities", os.path.join(os.path.dirname(os.path.abspath(__file__)), "cities_list.py"))
cl = importlib.util.module_from_spec(spec); spec.loader.exec_module(cl)
CITIES = cl.CITIES

HERE = os.path.dirname(os.path.abspath(__file__))
GEO = os.path.join(HERE, "data", "geo")        # 行政區界線 GeoJSON（見 tools/README.md，不放進 repo）
OUT = os.path.join(HERE, "out")
os.makedirs(OUT, exist_ok=True)
FINE = float(sys.argv[1]) if len(sys.argv) > 1 else 0.04
COARSE = 0.1      # 物理外框的簡化程度（越小越貼近繪圖輪廓，兩塊疊在一起的情形越少）
INFLATE = 0.02    # 物理外框再外擴一點點：寧可留一條細縫，也不要讓兩塊畫面上疊在一起
K = 0.84
SHARE = 0.55      # 某地級市有 55% 以上落在同一城的最近範圍內，就整塊歸給它

def load(name):
    return json.load(open(f"{GEO}/{name}.json", encoding="utf-8"))["features"]
from opencc import OpenCC
cc = OpenCC('t2s')
MUNI = {'11': '110000', '12': '120000', '31': '310000', '50': '500000'}
clip = box(98, 17, 125.5, 44)

# ---- 收集所有地級市多邊形（漢地範圍） ----
prefs, seen = [], set()
for name, f, z, parts in OLD_UNITS:
    for prov, keys in parts.items():
        if keys == 'M':
            for x in load(MUNI[prov]):
                k = (prov, x["properties"]["name"])
                if k not in seen:
                    seen.add(k); prefs.append((k, shape(x["geometry"]), x["properties"].get("adcode")))
            continue
        for x in load(prov):
            n = x["properties"]["name"]
            if keys == 'ALL' or any(cc.convert(k) in n for k in keys):
                k = (prov, n)
                if k not in seen:
                    seen.add(k); prefs.append((k, shape(x["geometry"]), x["properties"].get("adcode")))
prefs = [(k, g.buffer(0.012).intersection(clip), ad) for k, g, ad in prefs]
mask = unary_union([g for _, g, _ in prefs])
print("地級市數", len(prefs), "遮罩面積", round(mask.area, 1))

# ---- Voronoi 最近範圍 ----
names = [c[0] for c in CITIES]
pts = [Point(lon * K, lat) for *_, lon, lat in CITIES]
vor = voronoi_diagram(MultiPoint(pts), envelope=box(90*K, 10, 130*K, 50))
cells = {}
for cell in vor.geoms:
    for i, p in enumerate(pts):
        if cell.contains(p):
            cells[names[i]] = affinity.scale(cell, xfact=1/K, yfact=1, origin=(0, 0))

# ---- 縣級邊界：地級市被多座城瓜分時，改用縣（區）為單位指派，邊界仍是真實行政區線 ----
import subprocess
def county_feats(adcode):
    if not adcode: return None
    fp = f"{GEO}/c_{adcode}.json"
    if not os.path.exists(fp):
        tpl = os.environ.get("COUNTY_URL_TEMPLATE")
        if not tpl:
            return None
        r = subprocess.run(["curl", "-s", "-m", "30", "-A", "Mozilla/5.0", "-o", fp, "-w", "%{http_code}", tpl.format(adcode=adcode)], capture_output=True)
        if r.stdout.decode().strip() != "200":
            if os.path.exists(fp): os.remove(fp)
            return None
    try:
        return json.load(open(fp, encoding="utf-8"))["features"]
    except Exception:
        return None

site_pts = {n: Point(lon, lat) for n, f, z, lon, lat in CITIES}
assign = {n: [] for n in names}
split_log = []
def best_site(g, force=None):
    best, share = None, 0
    for n in names:
        a = g.intersection(cells[n]).area
        if a / g.area > share:
            best, share = n, a / g.area
    return best, share

for k, g, ad in prefs:
    if g.is_empty: continue
    inside = [n for n in names if g.contains(site_pts[n])]
    best, share = best_site(g)
    if len(inside) < 2 and share >= SHARE:
        assign[best].append(g); continue
    feats = county_feats(ad)
    if not feats:
        for n in names:
            piece = g.intersection(cells[n])
            if piece.area > 0.02: assign[n].append(piece)
        split_log.append((k[1], "直線切開（無縣級資料）", inside))
        continue
    cnt = {}
    for x in feats:
        cg = shape(x["geometry"]).buffer(0.004).intersection(g)
        if cg.is_empty: continue
        forced = [n for n in names if shape(x["geometry"]).contains(site_pts[n])]
        if forced:
            n = forced[0]
        else:
            n, sh = best_site(cg)
            if sh < SHARE:                      # 縣也被瓜分：只好沿 Voronoi 直線切
                for m in names:
                    piece = cg.intersection(cells[m])
                    if piece.area > 0.01: assign[m].append(piece)
                continue
        assign[n].append(cg); cnt[n] = cnt.get(n, 0) + 1
    split_log.append((k[1], "縣級", inside, cnt))
for t in split_log: print("跨城的地級市：", t)

geom = {}
for n in names:
    geom[n] = unary_union([g.buffer(0.004) for g in assign[n]]) if assign[n] else Polygon()

# ---- 太小或空的城：改用自己的 Voronoi 範圍，並從鄰城扣掉 ----
for n, f, z, lon, lat in CITIES:
    if geom[n].area < 0.5:
        cell = cells[n].intersection(mask)
        geom[n] = cell
        for o in names:
            if o != n and not geom[o].is_empty:
                geom[o] = geom[o].difference(cell.buffer(0.001))
        print("改用 Voronoi 範圍：", n, round(cell.area, 2))

# ---- 清理：每城只留包含城座標（或最大）的一塊，其餘碎塊併入相鄰城 ----
def comps(g):
    return [p for p in (list(g.geoms) if isinstance(g, MultiPolygon) else [g]) if p.geom_type == 'Polygon' and p.area > 0]
for rounds in range(2):
    for n, f, z, lon, lat in CITIES:
        cs = comps(geom[n])
        if len(cs) <= 1: continue
        main = next((p for p in cs if p.buffer(0.3).contains(Point(lon, lat))), max(cs, key=lambda p: p.area))
        geom[n] = main
        for p in cs:
            if p is main or p.area < 0.002: continue
            # 併入共邊最長的鄰城
            best, bl = None, 0
            for o in names:
                if o == n or geom[o].is_empty: continue
                l = p.buffer(0.03).intersection(geom[o]).area
                if l > bl: best, bl = o, l
            if best: geom[best] = unary_union([geom[best], p.buffer(0.004)])

raw = {}
for n in names:
    cs = comps(geom[n])
    big = max(cs, key=lambda p: p.area)
    raw[n] = Polygon(big.exterior)

def simp(tol):
    r = shapely.coverage_simplify([raw[n] for n in names], tol)
    o = {}
    for n, g in zip(names, r):
        if isinstance(g, MultiPolygon):
            g = max(g.geoms, key=lambda x: x.area)
        o[n] = Polygon(g.exterior)
    return o
fine = simp(FINE); coarse = simp(COARSE)
for n in names:
    g = coarse[n].buffer(INFLATE, join_style=2)
    if isinstance(g, MultiPolygon): g = max(g.geoms, key=lambda x: x.area)
    coarse[n] = Polygon(g.exterior).simplify(0.01)
# 標籤位置：多邊形內離邊界最遠的點（polylabel），避免標籤落在別人身上
labels = {}
for n in names:
    pt = shapely.polylabel(fine[n], 0.01) if hasattr(shapely, 'polylabel') else fine[n].representative_point()
    labels[n] = (round(pt.x, 3), round(pt.y, 3), round(fine[n].exterior.distance(pt), 3))

adj = []
for i, a in enumerate(names):
    for b in names[i+1:]:
        if raw[a].buffer(0.05).intersects(raw[b].buffer(0.05)):
            adj.append(f"{a}|{b}")
nb = {n: sum(1 for t in adj if n in t.split('|')) for n in names}
areas = sorted(((raw[n].area, n) for n in names), reverse=True)
print("單位數", len(names), "相鄰對數", len(adj))
print("沒有鄰居：", [n for n in names if nb[n] == 0], " 鄰居最少：", sorted(nb.items(), key=lambda t: t[1])[:6])
print("最大：", [(n, round(a, 1)) for a, n in areas[:6]])
print("最小：", [(n, round(a, 2)) for a, n in areas[-8:]])
print("頂點數 fine 合計：", sum(len(fine[n].exterior.coords) for n in names), " coarse：", sum(len(coarse[n].exterior.coords) for n in names))
# 站點是否落在自己的範圍內
off = [n for n, f, z, lon, lat in CITIES if not raw[n].buffer(0.5).contains(Point(lon, lat))]
print("座標不在自己範圍內：", off)

out = {"units": [{"n": n, "f": f, "z": z, "l": [labels[n][0], labels[n][1]], "r": labels[n][2],
                  "v": [[round(x, 2), round(y, 2)] for x, y in list(fine[n].exterior.coords)[:-1]],
                  "p": [[round(x, 2), round(y, 2)] for x, y in list(coarse[n].exterior.coords)[:-1]]}
                 for n, f, z, lon, lat in CITIES], "adj": adj}
json.dump(out, open(os.path.join(OUT, "cities_voronoi.json"), "w", encoding="utf-8"), ensure_ascii=False)
