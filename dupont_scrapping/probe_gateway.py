"""
Probe the DuPont Registry GraphQL gateway via introspection.
Run this to discover all available types and fields without any prior knowledge.
"""
import requests

GATEWAY = 'https://api-gateway.dupontregistry.com/graphql'

INTROSPECTION_QUERY = """
{
  __schema {
    types {
      name
      kind
      fields {
        name
        type {
          name
          kind
          ofType { name kind }
        }
      }
    }
  }
}
"""

resp = requests.post(
    GATEWAY,
    json={'query': INTROSPECTION_QUERY},
    headers={
        'Content-Type': 'application/json',
        'Accept':       'application/json',
        'User-Agent':   'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/149.0.0.0 Safari/537.36',
        'Origin':       'https://www.dupontregistry.com',
    },
    timeout=15,
)
resp.raise_for_status()

types = resp.json()['data']['__schema']['types']

for t in types:
    # skip built-in GraphQL types (they start with __)
    if t['name'].startswith('__') or not t['fields']:
        continue
    print(f"\n=== {t['name']} ({t['kind']}) ===")
    for f in t['fields']:
        ft = f['type']
        type_name = ft['name'] or (ft.get('ofType') or {}).get('name') or ''
        print(f"  {f['name']}: {type_name}")
