#!/usr/bin/env python3
"""Delete all _SLINECEK_ and ghost categories from Ikas."""
import os, requests, json, time, re
from collections import defaultdict

# Load env manually
env_path = "/app/backend/.env"
with open(env_path) as f:
    for line in f:
        line = line.strip()
        if "=" in line and not line.startswith("#"):
            k, v = line.split("=", 1)
            os.environ[k.strip()] = v.strip().strip('"')

IKAS_CLIENT_ID = os.environ.get("IKAS_CLIENT_ID")
IKAS_CLIENT_SECRET = os.environ.get("IKAS_CLIENT_SECRET")

token_resp = requests.post("https://api.myikas.com/api/admin/oauth/token", json={
    "grant_type": "client_credentials",
    "client_id": IKAS_CLIENT_ID,
    "client_secret": IKAS_CLIENT_SECRET,
}, timeout=10)
token = token_resp.json()["access_token"]


def gql(query, variables=None, t=120):
    resp = requests.post("https://api.myikas.com/api/v2/admin/graphql",
        json={"query": query, "variables": variables or {}},
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        timeout=t)
    data = resp.json()
    if data.get("errors"):
        return {"_errors": data["errors"]}
    return data.get("data", {})


cats = gql("{ listCategory { id name parentId } }", t=30).get("listCategory", [])
id_to_cat = {c["id"]: c for c in cats}
uuid_re = re.compile(r"^[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}")

to_delete = []
for c in cats:
    name = c["name"].strip()
    if name.startswith("_SLINECEK_"):
        to_delete.append(c["id"])
        continue
    chain = []
    cur = c
    visited = set()
    while cur and cur["id"] not in visited:
        visited.add(cur["id"])
        chain.append(cur["name"])
        cur = id_to_cat.get(cur.get("parentId"))
    if any(uuid_re.match(n) for n in chain):
        to_delete.append(c["id"])

print(f"{len(to_delete)} kategori silinecek")

# Delete one by one
deleted = 0
for did in to_delete:
    name = id_to_cat.get(did, {}).get("name", "?")
    try:
        r = gql(
            "mutation D($ids: [String!]!) { deleteCategoryList(idList: $ids) }",
            {"ids": [did]},
            t=120,
        )
        if r.get("_errors"):
            print(f"  X {name[:40]}: {r['_errors'][0].get('message','')[:50]}")
        else:
            deleted += 1
            print(f"  OK {name[:40]}")
    except Exception as e:
        print(f"  TIMEOUT {name[:40]}: {str(e)[:30]}")
    time.sleep(3)

print(f"\nSilindi: {deleted}/{len(to_delete)}")

# Final
try:
    cats2 = gql("{ listCategory { id name } }", t=30).get("listCategory", [])
    slinecek = [c for c in cats2 if c["name"].startswith("_SLINECEK_")]
    print(f"Kalan toplam: {len(cats2)}, _SLINECEK_: {len(slinecek)}")
except:
    print("Final kontrol timeout")
