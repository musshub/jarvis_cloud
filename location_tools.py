import math
from typing import Dict, Any, List
import requests

def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    radius = 6371.0
    p1 = math.radians(lat1); p2 = math.radians(lat2)
    dp = math.radians(lat2-lat1); dl = math.radians(lon2-lon1)
    a = math.sin(dp/2)**2 + math.cos(p1)*math.cos(p2)*math.sin(dl/2)**2
    return radius * 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))

def describe_location(lat: float, lon: float) -> Dict[str, Any]:
    try:
        res = requests.get("https://nominatim.openstreetmap.org/reverse", params={"format":"jsonv2","lat":lat,"lon":lon}, headers={"User-Agent":"ShubJarvisPersonal/1.0"}, timeout=20)
        res.raise_for_status(); data=res.json()
        return {"ok": True, "lat": lat, "lon": lon, "display_name": data.get("display_name"), "address": data.get("address", {})}
    except Exception as e:
        return {"ok": False, "lat": lat, "lon": lon, "error": str(e)}

def nearest_petrol_pumps(lat: float, lon: float, radius_m: int = 5000) -> Dict[str, Any]:
    query=f"""[out:json][timeout:25];(node[\"amenity\"=\"fuel\"](around:{radius_m},{lat},{lon});way[\"amenity\"=\"fuel\"](around:{radius_m},{lat},{lon});relation[\"amenity\"=\"fuel\"](around:{radius_m},{lat},{lon}););out center tags 20;"""
    try:
        res=requests.post("https://overpass-api.de/api/interpreter", data={"data":query}, headers={"User-Agent":"ShubJarvisPersonal/1.0"}, timeout=35)
        res.raise_for_status(); data=res.json(); places=[]
        for item in data.get("elements", []):
            item_lat=item.get("lat") or item.get("center",{}).get("lat")
            item_lon=item.get("lon") or item.get("center",{}).get("lon")
            if item_lat is None or item_lon is None: continue
            tags=item.get("tags",{}); name=tags.get("name") or tags.get("brand") or "Petrol pump"
            places.append({"name":name,"lat":item_lat,"lon":item_lon,"distance_km":round(haversine_km(lat,lon,float(item_lat),float(item_lon)),2),"brand":tags.get("brand"),"operator":tags.get("operator"),"address":tags.get("addr:full") or tags.get("addr:street")})
        places.sort(key=lambda x:x["distance_km"])
        return {"ok": True, "lat":lat,"lon":lon,"radius_m":radius_m,"places":places[:10]}
    except Exception as e:
        return {"ok": False, "lat":lat,"lon":lon,"error":str(e),"places":[]}
