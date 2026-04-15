"""Ingestion API endpoints."""

import logging
import os
import shutil
import tempfile
import time

from fastapi import APIRouter, File, HTTPException, UploadFile

from backend.app.services.ingestion import IngestionService
from backend.app.services.ingestion.ingest_job_store import ingest_job_store
from backend.app.services.ingestion.semantic_ingestion_service import SemanticIngestionService

router = APIRouter()


@router.post("/ingest")
async def ingest(
    file: UploadFile = File(..., description="PDF file to ingest"),
    mode: str = "semantic",
):
    """Ingest a PDF file into either semantic or legacy pipelines."""
    logger = logging.getLogger("uvicorn.error")
    started_at = time.perf_counter()

    if not file.filename:
        raise HTTPException(status_code=400, detail="No file provided")
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are supported.")

    safe_filename = "".join(c for c in file.filename if c.isalnum() or c in "._-")
    if not safe_filename:
        safe_filename = "uploaded_file.pdf"

    temp_dir = tempfile.gettempdir()
    temp_file_path = os.path.join(
        temp_dir, f"mindmap_ai_{os.urandom(8).hex()}_{safe_filename}"
    )

    try:
        logger.info("Ingest request accepted: file=%s mode=%s", file.filename, mode)
        job = ingest_job_store.create_job(file_name=file.filename, mode=mode)
        with open(temp_file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        original_filename = file.filename
        if mode == "legacy":
            service = IngestionService()
            try:
                ingest_job_store.update_stage(job.job_id, "parsing")
                logger.info("Legacy ingestion started: file=%s", original_filename)
                result = service.ingest_pdf(temp_file_path, original_filename)
                ingest_job_store.mark_completed(
                    job.job_id,
                    document_id=result.get("doc_id"),
                    details={"status": result.get("status")},
                )
                elapsed = time.perf_counter() - started_at
                logger.info(
                    "Legacy ingestion finished: file=%s status=%s doc_id=%s elapsed=%.2fs job_id=%s",
                    original_filename,
                    result.get("status"),
                    result.get("doc_id"),
                    elapsed,
                    job.job_id,
                )
                if result.get("saved_file_name"):
                    result["static_url"] = f"/static/{result['saved_file_name']}"
                result["ingest_job_id"] = job.job_id
                return result
            finally:
                service.close()

        service = SemanticIngestionService()
        logger.info("Semantic ingestion started: file=%s job_id=%s", original_filename, job.job_id)

        def on_stage(stage: str, details: dict | None = None) -> None:
            updated = ingest_job_store.update_stage(job.job_id, stage, details)
            if updated:
                logger.info(
                    "Ingest stage transition: job_id=%s file=%s stage=%s details=%s",
                    job.job_id,
                    original_filename,
                    stage,
                    details or {},
                )

        result = service.ingest_pdf(temp_file_path, original_filename, progress_callback=on_stage)
        ingest_job_store.mark_completed(
            job.job_id,
            document_id=result.document_id,
            details={"status": result.status},
        )
        elapsed = time.perf_counter() - started_at
        logger.info(
            "Semantic ingestion finished: file=%s status=%s document_id=%s elapsed=%.2fs job_id=%s",
            original_filename,
            result.status,
            result.document_id,
            elapsed,
            job.job_id,
        )
        response = result.to_dict()
        response["ingest_job_id"] = job.job_id
        if result.saved_file_name:
            response["static_url"] = f"/static/{result.saved_file_name}"
        return response
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=f"File not found: {exc}") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=f"Invalid input: {exc}") from exc
    except Exception as exc:
        if "job" in locals():
            ingest_job_store.mark_failed(job.job_id, str(exc))
        logger.error("Ingestion failed: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error processing PDF: {exc}") from exc
    finally:
        if os.path.exists(temp_file_path):
            try:
                os.remove(temp_file_path)
            except Exception as exc:
                logger.warning("Failed to remove temp file %s: %s", temp_file_path, exc)


@router.get("/ingest/{job_id}")
async def ingest_status(job_id: str):
    """Return stage-based status for an ingestion job."""
    job = ingest_job_store.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Ingest job not found")
    return job.to_dict()
