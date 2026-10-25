from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from backend.app.agents.agent3.submission import evaluate_submission_readiness
from backend.app.database.models import SubmissionArtifact, User
from backend.app.database.session import get_db
from backend.app.exports.report_generator import generate_full_submission_package
from backend.app.schemas.api_schemas import ExportCreateRequest
from backend.app.security.auth import get_current_user

router = APIRouter(prefix="/api/exports", tags=["Submission Exports"])


def _serialize_artifact(a: SubmissionArtifact) -> dict:
    return {
        "id": a.id,
        "export_batch_id": a.export_batch_id,
        "artifact_type": a.artifact_type,
        "file_name": a.file_name,
        "file_path": a.file_path,
        "status": a.status,
        "contains_synthetic_data": a.contains_synthetic_data,
        "record_count": a.record_count,
        "checksum_sha256": a.checksum_sha256,
        "notes": a.notes,
        "created_at": a.created_at.isoformat() if a.created_at else None,
        "download_url": f"/api/exports/{a.id}/download",
    }


@router.post("")
def generate_exports_endpoint(
    payload: ExportCreateRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    summary = generate_full_submission_package(
        db=db,
        include_synthetic=payload.include_synthetic,
    )
    batch_artifacts = (
        db.query(SubmissionArtifact)
        .filter(SubmissionArtifact.export_batch_id == summary["export_batch_id"])
        .all()
    )
    return {
        **summary,
        "artifacts": [_serialize_artifact(a) for a in batch_artifacts],
    }


@router.get("")
def list_exports(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    artifacts = (
        db.query(SubmissionArtifact)
        .order_by(SubmissionArtifact.created_at.desc())
        .limit(50)
        .all()
    )
    readiness = evaluate_submission_readiness(db)
    return {
        "readiness": readiness,
        "artifacts": [_serialize_artifact(a) for a in artifacts],
    }


@router.get("/{export_id}")
def get_export_metadata(
    export_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    art = db.query(SubmissionArtifact).filter(SubmissionArtifact.id == export_id).first()
    if art:
        return _serialize_artifact(art)

    batch_arts = (
        db.query(SubmissionArtifact)
        .filter(SubmissionArtifact.export_batch_id == export_id)
        .all()
    )
    if batch_arts:
        return {
            "export_batch_id": export_id,
            "artifacts": [_serialize_artifact(a) for a in batch_arts],
        }
    raise HTTPException(status_code=404, detail=f"Export '{export_id}' not found.")


@router.get("/{export_id}/download")
def download_export_file(
    export_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    art = db.query(SubmissionArtifact).filter(SubmissionArtifact.id == export_id).first()
    if not art:
        art = (
            db.query(SubmissionArtifact)
            .filter(
                SubmissionArtifact.export_batch_id == export_id,
                SubmissionArtifact.artifact_type == "SUBMISSION_ZIP_BUNDLE",
            )
            .first()
        )
    if not art:
        raise HTTPException(status_code=404, detail=f"Export artifact '{export_id}' not found.")

    fpath = Path(art.file_path)
    if not fpath.exists():
        raise HTTPException(status_code=404, detail=f"File not found on disk: {fpath}")

    return FileResponse(
        path=str(fpath),
        filename=art.file_name,
        media_type="application/octet-stream",
    )
