import requests

url = "https://www.dupontregistry.com/api/v1/en_US/cars/list"

headers = {
    "accept": "application/json, text/plain, */*",
    "referer": "https://www.dupontregistry.com/cars-for-sale/ferrari/all?condition=used&listing=dealer",
    "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/149.0.0.0 Safari/537.36",
}

params = {
    "brand": "ferrari",
    "condition": "used",
    "listing": "dealer",
    "limit": 100,
    "offset": 0,
}

r = requests.get(url, headers=headers, params=params)

print(r.status_code)
print(r.text[:2000])