import requests
resp = requests.post(
    'https://api-gateway.dupontregistry.com/graphql',
    json={
        'query': """
        { cars(limit:10 source:"es" includes:["modification"]
               filters:{brandAlias:{eq:"ferrari"} conditionCode:{eq:"used"} listingType:{eq:"dealer"}})
          { data { modification { driveTrainName fuelTypeAlias } } } }
        """
    },
    headers={'Content-Type':'application/json','Origin':'https://www.dupontregistry.com','User-Agent':'Mozilla/5.0'},
    timeout=15
)
for c in resp.json()['data']['cars']['data']:
    m = c['modification']
    print(repr(m.get('driveTrainName')), '|', repr(m.get('fuelTypeAlias')))
