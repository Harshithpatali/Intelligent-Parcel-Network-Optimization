from math import radians,sin,cos,asin,sqrt
import requests
from src.core.config import OSRM_BASE_URL

def haversine_km(lat1,lon1,lat2,lon2):
    r=6371.0088; p1,p2=radians(lat1),radians(lat2); dp,dl=radians(lat2-lat1),radians(lon2-lon1); a=sin(dp/2)**2+cos(p1)*cos(p2)*sin(dl/2)**2
    return 2*r*asin(sqrt(a))

def osrm_route_km(lat1,lon1,lat2,lon2,timeout=8):
    url=f'{OSRM_BASE_URL}/route/v1/driving/{lon1},{lat1};{lon2},{lat2}'
    try:
        r=requests.get(url,params={'overview':'false'},timeout=timeout); r.raise_for_status(); return float(r.json()['routes'][0]['distance'])/1000
    except Exception: return haversine_km(lat1,lon1,lat2,lon2)*1.22
