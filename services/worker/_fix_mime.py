import truststore; truststore.inject_into_ssl()
from dotenv import load_dotenv; load_dotenv()
import os, httpx, urllib3
urllib3.disable_warnings()

supa_url = os.environ["SUPABASE_URL"]
supa_key = os.environ["SUPABASE_SERVICE_ROLE_KEY"]

headers = {
    "apikey": supa_key,
    "Authorization": f"Bearer {supa_key}",
    "Content-Type": "application/json",
}
payload = {
    "id": "gpr-tabelas",
    "name": "gpr-tabelas",
    "public": False,
    "file_size_limit": 52428800,  # 50 MB
    "allowed_mime_types": [
        "text/csv",
        "text/plain",
        "application/csv",
        "application/octet-stream",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "application/pdf",
    ],
}
resp = httpx.put(
    f"{supa_url}/storage/v1/bucket/gpr-tabelas",
    headers=headers,
    json=payload,
    verify=False,
    timeout=30,
)
print(f"status={resp.status_code}")
print(f"body={resp.text}")
