# 地圖資料產生工具

這個資料夾放的是「把 77 座城的輪廓資料產生出來並寫回 `index.html`」的腳本。平常改遊戲不需要它，只有要新增、刪除或移動城池時才用。

## 流程

```
cities_list.py ─┐
units_v2.py   ──┼─> build_hybrid.py ──> out/cities_voronoi.json ─┐
data/geo/*.json ┘                                                 ├─> build_overseas.py ──> out/cities_final.json ──> inject_data.py ──> ../index.html
                                         data/ne_admin1.geojson ──┘
```

1. `cities_list.py`：每座城的名稱、勢力（W 魏／S 蜀／U 吳）、漢末所屬的州、座標。新增城池從這裡開始。
2. `units_v2.py`：各城涵蓋的現代地級市（用來決定漢地範圍）。
3. `build_hybrid.py`：依「離哪座城最近」（Voronoi）切出每座城的範圍，被多座城瓜分的地級市改用縣級界線指派；輸出 `out/cities_voronoi.json`。
4. `build_overseas.py`：加上隔海的夷州（臺灣）、邪馬台（北九州）、大和（畿內）與交趾（越南北部）；參考原版把離島挪到鄰近陸地旁的做法，輪廓平移到緊貼海岸／國界；輸出 `out/cities_final.json`。
5. `inject_data.py`：把結果寫回 `../index.html` 的 `STATES` 與 `ADJ_PAIRS`，不動成就與其他程式。可以給一個輸出路徑先試跑：`python inject_data.py 暫存.html`。

## 需要自備的輸入（不放進 repo，已在 `.gitignore`）

- `data/geo/`：現代行政區界線的 GeoJSON。省級檔案以省級代碼命名（例如 `13.json`、直轄市 `110000.json`），縣級檔案命名為 `c_<地級市代碼>.json`。缺縣級檔案時，被瓜分的地級市會改用直線切開；也可以設定環境變數 `COUNTY_URL_TEMPLATE`（網址中用 `{adcode}` 代表代碼），腳本就會自動下載缺的檔案。
- `data/ne_admin1.geojson`：Natural Earth 10m 的 admin-1 States and Provinces（公有領域），給臺灣、日本、越南用。

## 環境

Python 3.11 以上，需要 `shapely>=2`、`opencc-python-reimplemented`。Windows 上建議用 `python -X utf8` 執行，避免輸出亂碼。

```bash
python -X utf8 build_hybrid.py
python -X utf8 build_overseas.py
python -X utf8 inject_data.py
```

## 驗證

跑完後用瀏覽器開 `../index.html`：確認沒有錯誤、城數正確、所有成就用到的城名都存在、`ADJ_PAIRS` 沒有不存在的城。新增城池後還要用自動玩家重新校準難度（見根目錄說明）。
