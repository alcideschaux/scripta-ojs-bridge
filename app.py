import os
from typing import Any, Dict, Optional

import httpx
from fastapi import FastAPI, Header, HTTPException, Query


app = FastAPI(
    title="Scripta Scientia OJS Bridge",
    version="1.1.0",
    description="Bridge seguro para conectar GPT Actions con la API REST de OJS.",
)

OJS_BASE_URL = os.getenv("OJS_BASE_URL", "https://scriptascientia.com/sasc/api/v1").rstrip("/")
OJS_API_TOKEN = os.getenv("OJS_API_TOKEN")
BRIDGE_TOKEN = os.getenv("BRIDGE_TOKEN")


def check_auth(authorization: Optional[str]) -> None:
    if not BRIDGE_TOKEN:
        raise HTTPException(status_code=500, detail="BRIDGE_TOKEN not configured")

    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing Bearer token")

    token = authorization.replace("Bearer ", "", 1).strip()

    if token != BRIDGE_TOKEN:
        raise HTTPException(status_code=403, detail="Invalid bridge token")


async def call_ojs(path: str, params: Optional[Dict[str, Any]] = None) -> Any:
    if not OJS_API_TOKEN:
        raise HTTPException(status_code=500, detail="OJS_API_TOKEN not configured")

    query = dict(params or {})
    query["apiToken"] = OJS_API_TOKEN

    url = f"{OJS_BASE_URL}{path}"

    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.get(url, params=query)

    if response.status_code >= 400:
        raise HTTPException(
            status_code=response.status_code,
            detail={
                "ojs_status_code": response.status_code,
                "ojs_response": response.text,
            },
        )

    try:
        return response.json()
    except ValueError:
        return {"raw": response.text}


def localized_value(value: Any) -> Any:
    if isinstance(value, dict):
        return value.get("es") or value.get("en") or next(iter(value.values()), None)
    return value


def summarize_submission(item: Dict[str, Any]) -> Dict[str, Any]:
    publications = item.get("publications") or []
    publication = publications[0] if publications else {}

    title = (
        publication.get("title")
        or item.get("title")
        or item.get("fullTitle")
        or {}
    )

    return {
        "id": item.get("id"),
        "status": item.get("status"),
        "statusLabel": item.get("statusLabel"),
        "dateSubmitted": item.get("dateSubmitted"),
        "lastModified": item.get("lastModified"),
        "title": localized_value(title),
        "currentPublicationId": item.get("currentPublicationId"),
        "stageId": item.get("stageId"),
        "url": item.get("_href"),
    }


@app.get("/health")
def health():
    return {
        "status": "ok",
        "service": "scripta-ojs-bridge",
        "version": "1.1.0",
        "ojs_base_url": OJS_BASE_URL,
    }


@app.get("/issues")
async def list_issues(
    authorization: Optional[str] = Header(default=None),
    count: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
):
    check_auth(authorization)
    return await call_ojs("/issues", {"count": count, "offset": offset})


@app.get("/issues/{issue_id}")
async def get_issue(
    issue_id: int,
    authorization: Optional[str] = Header(default=None),
):
    check_auth(authorization)
    return await call_ojs(f"/issues/{issue_id}")


@app.get("/submissions")
async def list_submissions(
    authorization: Optional[str] = Header(default=None),
    count: int = Query(default=5, ge=1, le=20),
    offset: int = Query(default=0, ge=0),
    searchPhrase: Optional[str] = Query(default=None),
    status: Optional[int] = Query(default=None),
):
    check_auth(authorization)

    params: Dict[str, Any] = {"count": count, "offset": offset}

    if searchPhrase:
        params["searchPhrase"] = searchPhrase

    if status is not None:
        params["status"] = status

    data = await call_ojs("/submissions", params)

    items = data.get("items", []) if isinstance(data, dict) else []

    return {
        "items": [summarize_submission(item) for item in items],
        "itemsMax": data.get("itemsMax") if isinstance(data, dict) else None,
        "count": count,
        "offset": offset,
    }


@app.get("/submissions/{submission_id}")
async def get_submission(
    submission_id: int,
    authorization: Optional[str] = Header(default=None),
):
    check_auth(authorization)
    return await call_ojs(f"/submissions/{submission_id}")


@app.get("/submissions/{submission_id}/publications")
async def list_submission_publications(
    submission_id: int,
    authorization: Optional[str] = Header(default=None),
):
    check_auth(authorization)
    return await call_ojs(f"/submissions/{submission_id}/publications")


@app.get("/submissions/{submission_id}/participants")
async def list_submission_participants(
    submission_id: int,
    authorization: Optional[str] = Header(default=None),
):
    check_auth(authorization)
    return await call_ojs(f"/submissions/{submission_id}/participants")


@app.get("/submissions/{submission_id}/files")
async def list_submission_files(
    submission_id: int,
    authorization: Optional[str] = Header(default=None),
    fileStage: Optional[int] = Query(default=None),
):
    check_auth(authorization)

    params: Dict[str, Any] = {}
    if fileStage is not None:
        params["fileStage"] = fileStage

    return await call_ojs(f"/submissions/{submission_id}/files", params)


@app.get("/users")
async def list_users(
    authorization: Optional[str] = Header(default=None),
    count: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    searchPhrase: Optional[str] = Query(default=None),
):
    check_auth(authorization)

    params: Dict[str, Any] = {"count": count, "offset": offset}
    if searchPhrase:
        params["searchPhrase"] = searchPhrase

    return await call_ojs("/users", params)


@app.get("/users/{user_id}")
async def get_user(
    user_id: int,
    authorization: Optional[str] = Header(default=None),
):
    check_auth(authorization)
    return await call_ojs(f"/users/{user_id}")
