import asyncio, httpx, os
async def main():
    headers = {"Authorization": f"Bearer {os.environ['SERVER_API_KEY']}", "X-Tenant-Id": os.environ["TENANT_ID"]}
    async with httpx.AsyncClient(base_url=os.environ["SERVER_API_URL"], headers=headers, timeout=10) as c:
        for p in ["meeting-asr","meeting-minutes","meeting-knowledge-extract","meeting-embedding"]:
            r = await c.post("/api/v1/models/profiles/resolve", json={"profile_name": p})
            print(f"  {p}: {r.status_code} {r.json().get('deployment_id','?') if r.status_code==200 else r.text[:80]}")
asyncio.run(main())
