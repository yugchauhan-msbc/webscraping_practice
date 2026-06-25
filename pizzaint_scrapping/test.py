import json
import uuid
import requests

API_URL = "https://www.dupontregistry.com/api/graphql"

REFERER = "https://www.dupontregistry.com/cars-for-sale/ferrari/all?condition=used&listing=dealer"

HEADERS = {
    "accept": "application/graphql-response+json,application/json;q=0.9",
    "accept-language": "en-GB,en-US;q=0.9,en;q=0.8",
    "content-type": "application/json",
    "origin": "https://www.dupontregistry.com",
    "referer": REFERER,
    "sec-ch-prefers-color-scheme": "light",
    "sec-ch-ua": '"Google Chrome";v="149", "Chromium";v="149", "Not)A;Brand";v="24"',
    "sec-ch-ua-mobile": "?0",
    "sec-ch-ua-platform": '"Windows"',
    "sec-fetch-dest": "empty",
    "sec-fetch-mode": "cors",
    "sec-fetch-site": "same-origin",
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
    "data.year",
    "data.price",
    "data.vin",
    "data.mileage",
    "data.brand.name",
    "data.model.name",
    "data.dealer.name",
    "data.condition.code",
    "data.promotionTypeName",
])


def fetch(limit, listing_type="dealer"):
    headers = dict(HEADERS)
    headers["x-request-id"] = str(uuid.uuid4())

    inner_variables = {
        "source": "es",
        "cache": True,
        "limit": limit,
        "filters": {
            "brandAlias": {"in": ["ferrari"]},
            "conditionCode": {"eq": "used"},
            "listingType": {"in": [listing_type]},
        },
    }

    payload = {
        "operationName": "ExecuteQuery2",
        "variables": {
            "queryName": "promotedCars",
            "fields": FIELDS,
            "variables": json.dumps(inner_variables),
        },
        "extensions": {
            "clientLibrary": {
                "name": "@apollo/client",
                "version": "4.0.2",
            }
        },
        "query": QUERY,
    }

    response = requests.post(API_URL, headers=headers, json=payload, timeout=30)

    print("HTTP status:", response.status_code)

    if response.status_code != 200:
        print(response.text[:1000])
        return []

    outer = response.json()
    raw = outer.get("data", {}).get("executeQuery2")

    if not raw:
        print("No data returned:")
        print(json.dumps(outer, indent=2)[:2000])
        return []

    parsed = json.loads(raw)
    return parsed.get("promotedCars", {}).get("data", [])


def main():
    for listing_type in ["dealer", "private"]:
        print("\n" + "#" * 100)
        print("LISTING TYPE:", listing_type)

        previous_unique = 0

        for limit in [10, 20, 50, 100, 150, 200, 300, 500, 1000]:
            cars = fetch(limit=limit, listing_type=listing_type)
            unique_car_ids = {c.get("carId") for c in cars if c.get("carId")}

            print("=" * 80)
            print("Limit       :", limit)
            print("Rows        :", len(cars))
            print("Unique cars :", len(unique_car_ids))

            if len(unique_car_ids) == previous_unique:
                print("New cars    : 0")
            else:
                print("New cars    :", len(unique_car_ids) - previous_unique)

            previous_unique = len(unique_car_ids)


if __name__ == "__main__":
    main()