import geopandas as gpd
from shapely.geometry import Polygon, MultiPolygon
import requests
import json


south, west, north, east = 52.3700, 4.8950, 52.3800, 4.9050

def fetch_osm_geometries(overpass_query):
    overpass_url = "http://overpass-api.de/api/interpreter"
    try:
        response = requests.get(overpass_url, params={"data": overpass_query}, timeout=60)
        response.raise_for_status()
        data = response.json()
        with open(r'/media/ajay/master/GIS Project/osm_extection_with_parameter/data/reponse_log.json', "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        return data.get("elements", [])
    except Exception as e:
        print(f"Overpass error: {e}")
        return []

def elements_to_geometries(elements):
    geoms = []
    for elem in elements:
        if elem["type"] == "way" and "geometry" in elem:
            coords = [(pt["lon"], pt["lat"]) for pt in elem["geometry"]]
            try:
                poly = Polygon(coords)
                if not poly.is_empty:
                    geoms.append(poly)
            except:
                continue
        elif elem["type"] == "relation" and "members" in elem:
            parts = []
            for member in elem["members"]:
                if member["type"] == "way" and "geometry" in member:
                    coords = [(pt["lon"], pt["lat"]) for pt in member["geometry"]]
                    try:
                        parts.append(Polygon(coords))
                    except:
                        continue
            if parts:
                union = MultiPolygon([p for p in parts if not p.is_empty])
                if not union.is_empty:
                    geoms.append(union)
    return geoms

building_query = f"""
[out:json][timeout:60];
(
  way["building"]({south},{west},{north},{east});
  relation["building"]({south},{west},{north},{east});
);
out geom;
"""

green_query = f"""
[out:json][timeout:60];
(
  way["leisure"="park"]({south},{west},{north},{east});
  way["landuse"="grass"]({south},{west},{north},{east});
  way["landuse"="forest"]({south},{west},{north},{east});
);
out geom;
"""

water_query = f"""
[out:json][timeout:60];
(
  way["natural"="water"]({south},{west},{north},{east});
  way["waterway"]({south},{west},{north},{east});
);
out geom;
"""

building_elements = fetch_osm_geometries(building_query)
green_elements = fetch_osm_geometries(green_query)
water_elements = fetch_osm_geometries(water_query)

building_geoms = elements_to_geometries(building_elements)
green_geoms = elements_to_geometries(green_elements)
water_geoms = elements_to_geometries(water_elements)

building_gdf = gpd.GeoDataFrame(geometry=gpd.GeoSeries(building_geoms), crs="EPSG:4326")
green_gdf = gpd.GeoDataFrame(geometry=gpd.GeoSeries(green_geoms), crs="EPSG:4326")
water_gdf = gpd.GeoDataFrame(geometry=gpd.GeoSeries(water_geoms), crs="EPSG:4326")

building_gdf["is_valid"] = building_gdf.geometry.is_valid
valid_buildings = building_gdf[building_gdf["is_valid"]].copy()
invalid_buildings = building_gdf[~building_gdf["is_valid"]].copy()

building_gdf["status"] = building_gdf["is_valid"].map({True: "valid", False: "invalid"})
building_gdf.to_file("/media/ajay/master/GIS Project/osm_extection_with_parameter/output/all_buildings.geojson", driver="GeoJSON")

valid_proj = valid_buildings.to_crs(epsg=28992)
valid_proj["area"] = valid_proj.geometry.area
valid_proj = valid_proj[valid_proj["area"] >= 90]

valid_back = valid_proj.to_crs(epsg=4326)

green_union = green_gdf.geometry.buffer(0).union_all()
water_union = water_gdf.geometry.buffer(0).union_all()

final_filtered = valid_back[
    ~valid_back.geometry.intersects(green_union) &
    ~valid_back.geometry.intersects(water_union)
]

final_filtered.to_file("/media/ajay/master/GIS Project/osm_extection_with_parameter/output/filtered_buildings.geojson", driver="GeoJSON")

combined_map = final_filtered.explore(
    color="green",
    tooltip=False,
    name="Valid Buildings"
)

invalid_buildings.explore(
    color="red",
    tooltip=False,
    name="Invalid Buildings",
    m=combined_map
)

combined_map.save("/media/ajay/master/GIS Project/osm_extection_with_parameter/output/buildings_map.html")
