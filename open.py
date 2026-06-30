import requests

resp = requests.get(
    'https://openrouter.ai/api/frontend/v1/rankings/market-share?view=week',
    headers={'User-Agent': 'Mozilla/5.0', 'Referer': 'https://openrouter.ai/rankings'},
    timeout=30,
)
resp.raise_for_status()

weeks = resp.json()['data']

# print last week only
last = weeks[-2]
print('Date:', last['x'])
print()

total = sum(last['ys'].values())
for author, tokens in last['ys'].items():
    share = round(tokens / total * 100, 2)
    print(f'{author:<20} tokens={tokens:<15,} share={share}%')
