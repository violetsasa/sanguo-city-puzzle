"""在新產生的 73 座城（cities_voronoi.json）之外，加上交趾（越南北部）與三座島（夷州、邪馬台、大和）。"""
import json, sys, unicodedata
import shapely
from shapely.geometry import shape, Polygon, MultiPolygon
from shapely.ops import unary_union, nearest_points
from shapely import affinity

import os
HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "out")
DATA = os.path.join(HERE, "data")
FINE, COARSE, INFLATE = 0.04, 0.1, 0.02

base = json.load(open(os.path.join(OUT, "cities_voronoi.json"), encoding='utf-8'))
exist = {u['n']: Polygon(u['v']).buffer(0) for u in base['units']}
print('底圖', len(exist), '座')

fc = json.load(open(os.path.join(DATA, "ne_admin1.geojson"), encoding='utf-8'))
norm = lambda t: unicodedata.normalize('NFKD', t or '').encode('ascii', 'ignore').decode()
def feats(pred):
    return [shape(f['geometry']) for f in fc['features'] if pred(f['properties'])]
def biggest(g):
    return max(g.geoms, key=lambda x: x.area) if isinstance(g, MultiPolygon) else g

tw = unary_union(feats(lambda p: p.get('iso_a2') == 'TW' or p.get('admin') == 'Taiwan'))
jp = {}
for nm in ['Fukuoka', 'Saga', 'Nagasaki', 'Nara', 'Osaka', 'Wakayama']:
    jp[nm] = unary_union(feats(lambda p, nm=nm: p.get('admin') == 'Japan' and norm(p.get('name')) == nm))
VN = ['Ha Noi', 'Hai Phong', 'Bac Ninh', 'Hai Duong', 'Hung Yen', 'Thai Binh', 'Nam Dinh', 'Ha Nam', 'Ninh Binh', 'Vinh Phuc', 'Bac Giang', 'Quang Ninh', 'Lang Son']
vn_parts = feats(lambda p: p.get('admin') == 'Vietnam' and norm(p.get('name')) in VN)
print('越南北部省數', len(vn_parts))
jiaozhi = biggest(unary_union(vn_parts))

yizhou = biggest(tw)
yamatai = biggest(unary_union([jp['Fukuoka'], jp['Saga'], jp['Nagasaki']]))
yamato = biggest(unary_union([jp['Nara'], jp['Osaka'], jp['Wakayama']]))

GAP = 0.03
def touch(poly, target, gap=GAP):
    a, b = nearest_points(poly, target)
    dx, dy = b.x - a.x, b.y - a.y
    p2 = affinity.translate(poly, dx, dy)
    for _ in range(600):
        if p2.intersection(target).area <= 1e-9 and p2.distance(target) >= gap: break
        c1, c2 = p2.centroid, target.centroid
        vx, vy = c1.x - c2.x, c1.y - c2.y
        L = (vx * vx + vy * vy) ** 0.5 or 1
        p2 = affinity.translate(p2, vx / L * 0.005, vy / L * 0.005); dx += vx / L * 0.005; dy += vy / L * 0.005
    return p2, (dx, dy)

# 交趾：與中國合浦、布山接壤。兩套資料的國界略有出入，先平移貼合，再扣掉任何重疊
china_south = unary_union([exist['合浦'], exist['布山']])
jz, dj = touch(jiaozhi, china_south)
print('交趾位移', tuple(round(x, 2) for x in dj), '重疊', round(jz.intersection(unary_union(list(exist.values()))).area, 4))

yizhou2, d1 = touch(yizhou, exist['建安'])
yamatai2, d2 = touch(yamatai, unary_union([exist['會稽'], exist['建安']]))
n = 0
while yamatai2.distance(yizhou2) < 0.1 and n < 400:
    yamatai2 = affinity.translate(yamatai2, 0.0, 0.02); n += 1
yamato2, d3 = touch(yamato, yamatai2)
print('位移', {'夷州': tuple(round(x, 2) for x in d1), '邪馬台': tuple(round(x, 2) for x in d2), '大和': tuple(round(x, 2) for x in d3)})

new = {'交趾': jz, '夷州': yizhou2, '邪馬台': yamatai2, '大和': yamato2}
for n_, g in new.items():
    ov = [(k, round(g.intersection(v).area, 4)) for k, v in exist.items() if g.intersection(v).area > 1e-6]
    oth = [(m, round(g.intersection(h).area, 4)) for m, h in new.items() if m != n_ and g.intersection(h).area > 1e-6]
    near = sorted([(k, round(g.distance(v), 3)) for k, v in exist.items()], key=lambda t: t[1])[:3]
    print(n_, '面積', round(g.area, 2), '重疊現有城', ov, '重疊新城', oth, '最近', near, 'bbox', [round(x, 2) for x in g.bounds])

spec = [('交趾', 'U', '交州'), ('夷州', 'U', '夷洲'), ('邪馬台', 'W', '邪馬台'), ('大和', 'W', '大和')]   # 島上的城各自一個 z（單座不會產生「某某平定」的自動成就）
out = []
for n_, f, z in spec:
    g = Polygon(new[n_].exterior)
    fine = g.simplify(FINE)
    if isinstance(fine, MultiPolygon): fine = max(fine.geoms, key=lambda x: x.area)
    coarse = g.simplify(COARSE).buffer(INFLATE, join_style=2)
    if isinstance(coarse, MultiPolygon): coarse = max(coarse.geoms, key=lambda x: x.area)
    coarse = Polygon(coarse.exterior).simplify(0.01)
    try:
        from shapely.algorithms.polylabel import polylabel as _pl
        pt = _pl(fine, 0.01)
    except Exception:
        pt = fine.representative_point()
    lab = [round(pt.x, 3), round(pt.y, 3), round(fine.exterior.distance(pt), 3)]
    out.append({'n': n_, 'f': f, 'z': z, 'l': lab[:2], 'r': lab[2],
                'v': [[round(x, 2), round(y, 2)] for x, y in list(fine.exterior.coords)[:-1]],
                'p': [[round(x, 2), round(y, 2)] for x, y in list(coarse.exterior.coords)[:-1]]})
    print(n_, '頂點 v', len(out[-1]['v']), 'p', len(out[-1]['p']), '標籤', lab)

# 鄰接：外擴 0.05 度有交集，加上指定的跨海連結
adj = list(base['adj'])
raws = {**exist, **{o['n']: Polygon(o['v']).buffer(0) for o in out}}
for o in out:
    for k, v in raws.items():
        if k == o['n']: continue
        if raws[o['n']].buffer(0.05).intersects(v.buffer(0.05)):
            adj.append(f"{o['n']}|{k}")
adj = sorted(set(adj + ['夷州|建安', '邪馬台|會稽', '大和|邪馬台']))
units = base['units'] + out
nb = {u['n']: sum(1 for t in adj if u['n'] in t.split('|')) for u in units}
print('總單位', len(units), '鄰接對', len(adj), '鄰居最少', sorted(nb.items(), key=lambda t: t[1])[:5])
print('交趾鄰居', [t for t in adj if '交趾' in t])
json.dump({'units': units, 'adj': adj}, open(os.path.join(OUT, "cities_final.json"), 'w', encoding='utf-8'), ensure_ascii=False)
print('saved cities_final.json')
