import os
from typing import Any, Dict, List, Optional

import httpx
from fastapi import FastAPI, Header, HTTPException, Query


app = FastAPI(
    title="Scripta Scientia OJS Bridge",
    version="1.3.0",
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


def get_items(data: Any) -> List[Dict[str, Any]]:
    if isinstance(data, dict) and isinstance(data.get("items"), list):
        return data["items"]
    if isinstance(data, list):
        return data
    return []


def summarize_submission(item: Dict[str, Any]) -> Dict[str, Any]:
    publications = item.get("publications") or []
    publication = publications[0] if publications else {}

    title = publication.get("title") or item.get("title") or item.get("fullTitle") or {}

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


def summarize_publication(publication: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "id": publication.get("id"),
        "title": localized_value(publication.get("title")),
        "abstract": localized_value(publication.get("abstract")),
        "keywords": publication.get("keywords"),
        "authorsString": publication.get("authorsString"),
        "datePublished": publication.get("datePublished"),
        "sectionId": publication.get("sectionId"),
        "doiObject": publication.get("doiObject"),
        "urlPath": publication.get("urlPath"),
    }


def summarize_participant(participant: Dict[str, Any]) -> Dict[str, Any]:
    user = participant.get("user") or participant

    return {
        "id": participant.get("id") or user.get("id"),
        "userId": participant.get("userId") or user.get("id"),
        "name": user.get("fullName") or user.get("name"),
        "email": user.get("email"),
        "roles": participant.get("roles") or participant.get("roleIds"),
        "stageAssignmentId": participant.get("stageAssignmentId"),
        "dateAssigned": participant.get("dateAssigned"),
    }


def summarize_file(file_item: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "id": file_item.get("id"),
        "submissionFileId": file_item.get("submissionFileId"),
        "name": localized_value(file_item.get("name")),
        "genreId": file_item.get("genreId"),
        "fileStage": file_item.get("fileStage"),
        "documentType": file_item.get("documentType"),
        "mimetype": file_item.get("mimetype"),
        "dateUploaded": file_item.get("dateUploaded"),
        "url": file_item.get("_href"),
    }


def detect_editorial_signals(
    submission_summary: Dict[str, Any],
    publications: List[Dict[str, Any]],
    participants: List[Dict[str, Any]],
    files: List[Dict[str, Any]],
) -> Dict[str, Any]:
    file_names = " | ".join(str(f.get("name") or "").lower() for f in files)

    has_main_manuscript = any(
        term in file_names
        for term in ["articulo", "artículo", "manuscrito", "manuscript", ".docx", ".doc", ".pdf"]
    )

    has_front_page = any(
        term in file_names
        for term in ["primera hoja", "hoja frontal", "front", "cover", "title page"]
    )

    has_abstract = any(bool(p.get("abstract")) for p in publications)
    has_keywords = any(bool(p.get("keywords")) for p in publications)
    has_doi = any(bool(p.get("doiObject")) for p in publications)

    return {
        "hasMainManuscript": has_main_manuscript,
        "hasFrontPageOrCoverFile": has_front_page,
        "hasAbstractInMetadata": has_abstract,
        "hasKeywordsInMetadata": has_keywords,
        "hasDoiInMetadata": has_doi,
        "fileCount": len(files),
        "participantCount": len(participants),
        "publicationVersionCount": len(publications),
        "currentStageId": submission_summary.get("stageId"),
        "currentStatus": submission_summary.get("status"),
        "requiresHumanManuscriptReview": True,
        "notes": [
            "La revisión consolidada resume metadatos OJS, participantes, publicaciones y archivos.",
            "El contenido completo del manuscrito no se extrae todavía desde los archivos cargados.",
            "Las decisiones editoriales deben confirmarse revisando el documento principal.",
        ],
    }


@app.get("/health")
def health():
    return {
        "status": "ok",
        "service": "scripta-ojs-bridge",
        "version": "1.3.0",
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
    items = get_items(data)

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


@app.get("/editorial-review/{submission_id}")
async def editorial_review(
    submission_id: int,
    authorization: Optional[str] = Header(default=None),
):
    check_auth(authorization)

    submission = await call_ojs(f"/submissions/{submission_id}")
    publications_raw = await call_ojs(f"/submissions/{submission_id}/publications")
    participants_raw = await call_ojs(f"/submissions/{submission_id}/participants")
    files_raw = await call_ojs(f"/submissions/{submission_id}/files")

    submission_summary = summarize_submission(submission if isinstance(submission, dict) else {})
    publications = [summarize_publication(p) for p in get_items(publications_raw)]
    participants = [summarize_participant(p) for p in get_items(participants_raw)]
    files = [summarize_file(f) for f in get_items(files_raw)]

    signals = detect_editorial_signals(
        submission_summary=submission_summary,
        publications=publications,
        participants=participants,
        files=files,
    )

    return {
        "submissionId": submission_id,
        "submission": submission_summary,
        "publications": publications,
        "participants": participants,
        "files": files,
        "editorialSignals": signals,
        "recommendedUse": {
            "instruction": "Use this object to produce an editorial triage. Do not invent manuscript content not present in the metadata or files list.",
            "minimumNextSteps": [
                "Verify author metadata and uploaded files.",
                "Check whether the main manuscript and front page are present.",
                "Identify missing metadata such as abstract, keywords, ORCID, ethics approval, conflicts of interest, and funding.",
                "Recommend whether to request corrections before peer review or proceed to editor assignment.",
            ],
        },
    }


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
