import json
import requests
from pprint import pprint

API_URL = "https://www.dupontregistry.com/api/graphql"

HEADERS = {
    "accept": "application/graphql-response+json,application/json;q=0.9",
    "accept-language": "en-GB,en-US;q=0.9,en;q=0.8",
    "content-type": "application/json",
    "origin": "https://www.dupontregistry.com",
    "referer": "https://www.dupontregistry.com/cars-for-sale/ferrari/all?condition=used&listing=dealer",
    "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/149.0.0.0 Safari/537.36",
    "x-session-id": "anonymous-hash-62ec6c51e46eaade",
}

QUERY = """
query ExecuteQuery2($queryName: String!, $fields: String!, $variables: String) {
  executeQuery2(queryName: $queryName, fields: $fields, variables: $variables)
}
"""

FIELDS = ",".join([
    "data.id",
    "data.carId",
    "data.promoted",
    "data.promotionTypeId",
    "data.promotionTypeName",
    "data.year",
    "data.price",
    "data.vin",
    "data.mileage",
    "data.mainImageUrl",
    "data.brand.id",
    "data.brand.name",
    "data.brand.alias",
    "data.model.id",
    "data.model.name",
    "data.model.alias",
    "data.dealer.id",
    "data.dealer.name",
    "data.dealer.preferredDealerStatus",
    "data.locations.address",
    "data.locations.city",
    "data.locations.state",
    "data.locations.zipCode",
    "data.locations.metro",
    "data.locations.metroAlias",
    "data.locations.geoPoint.lat",
    "data.locations.geoPoint.lon",
    "data.locations.phone",
    "data.condition.code",
    "data.certified",
])


def call_api(query_name, listing_type="dealer", extra_vars=None):
    inner_vars = {
        "source": "es",
        "cache": True,
        "limit": 50,
        "filters": {
            "brandAlias": {"in": ["ferrari"]},
            "conditionCode": {"eq": "used"},
            "listingType": {"in": [listing_type]},
        },
    }

    if extra_vars:
        inner_vars.update(extra_vars)

    payload = {
        "operationName": "ExecuteQuery2",
        "variables": {
            "queryName": query_name,
            "fields": FIELDS,
            "variables": json.dumps(inner_vars),
        },
        "extensions": {
            "clientLibrary": {
                "name": "@apollo/client",
                "version": "4.0.2",
            }
        },
        "query": QUERY,
    }

    response = requests.post(API_URL, headers=HEADERS, json=payload, timeout=30)

    print("\n" + "=" * 90)
    print("queryName:", query_name)
    print("listingType:", listing_type)
    print("extraVars:", extra_vars)
    print("Status:", response.status_code)

    if response.status_code != 200:
        print(response.text[:1000])
        return []

    outer = response.json()
    raw = outer.get("data", {}).get("executeQuery2")

    if not raw:
        print("No executeQuery2 returned")
        pprint(outer)
        return []

    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        print("executeQuery2 is not JSON")
        print(raw[:1000])
        return []

    pprint(parsed.keys())

    data_block = parsed.get(query_name) or parsed.get("promotedCars") or parsed

    if isinstance(data_block, dict):
        cars = data_block.get("data", [])
    elif isinstance(data_block, list):
        cars = data_block
    else:
        cars = []

    print("Cars fetched:", len(cars))

    if cars:
        print("First car:")
        pprint(cars[0])

        vins = {x.get("vin") for x in cars if x.get("vin")}
        car_ids = {x.get("carId") for x in cars if x.get("carId")}
        print("Unique VINs:", len(vins))
        print("Unique carIds:", len(car_ids))

    return cars


def test_listing_types():
    for listing_type in ["dealer", "private"]:
        call_api("promotedCars", listing_type=listing_type)


def test_query_names():
    query_names = [
        "promotedCars",
        "cars",
        "searchCars",
        "carSearch",
        "inventory",
        "searchResults",
        "vehicles",
        "vehicleSearch",
        "listings",
    ]

    for query_name in query_names:
        call_api(query_name, listing_type="dealer")


def test_pagination():
    tests = [
        {},
        {"offset": 50},
        {"offset": 100},
        {"page": 2},
        {"page": 3},
        {"from": 50},
        {"from": 100},
        {"skip": 50},
    ]

    seen = set()

    for extra in tests:
        cars = call_api("promotedCars", listing_type="dealer", extra_vars=extra)

        ids = tuple(x.get("carId") for x in cars)
        print("Same as previous page?", ids in seen)
        seen.add(ids)


if __name__ == "__main__":
    print("TEST 1: Dealer + Private")
    test_listing_types()

    print("\n\nTEST 2: Possible query names")
    test_query_names()

    print("\n\nTEST 3: Pagination attempts")
    test_pagination()