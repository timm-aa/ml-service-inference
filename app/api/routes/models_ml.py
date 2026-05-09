from __future__ import annotations

import os
import shutil
import uuid

import joblib
from fastapi import APIRouter, Depends, File, Form, HTTPException, Response, UploadFile, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.config import get_settings
from app.database import get_db
from app.models import MLModel, User
from app.schemas import MLModelOut

router = APIRouter(prefix="/models", tags=["models"])


def _validate_sklearn_model(path: str) -> None:
    obj = joblib.load(path)
    if not hasattr(obj, "predict"):
        raise HTTPException(status_code=400, detail="Uploaded object must have predict()")


@router.post("", response_model=MLModelOut, status_code=status.HTTP_201_CREATED)
async def upload_model(
    name: str = Form(...),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> MLModel:
    settings = get_settings()
    os.makedirs(settings.model_storage_path, exist_ok=True)
    ext = os.path.splitext(file.filename or "")[1].lower()
    if ext not in (".pkl", ".joblib", ".pickle"):
        raise HTTPException(status_code=400, detail="Use .pkl or .joblib extension")
    fname = f"{uuid.uuid4().hex}{ext}"
    dest = os.path.join(settings.model_storage_path, fname)
    try:
        with open(dest, "wb") as out:
            shutil.copyfileobj(file.file, out)
        _validate_sklearn_model(dest)
    except HTTPException:
        if os.path.isfile(dest):
            os.remove(dest)
        raise
    except Exception as e:
        if os.path.isfile(dest):
            os.remove(dest)
        raise HTTPException(status_code=400, detail=f"Invalid model file: {e}") from e

    rec = MLModel(owner_id=user.id, name=name[:255], storage_filename=fname)
    db.add(rec)
    db.commit()
    db.refresh(rec)
    return rec


@router.get("", response_model=list[MLModelOut])
def list_models(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[MLModel]:
    rows = db.query(MLModel).filter(MLModel.owner_id == user.id).order_by(MLModel.id.desc()).all()
    return rows


@router.delete("/{model_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_model(
    model_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Response:
    m = db.get(MLModel, model_id)
    if m is None or m.owner_id != user.id:
        raise HTTPException(status_code=404, detail="Model not found")
    settings = get_settings()
    path = os.path.join(settings.model_storage_path, m.storage_filename)
    db.delete(m)
    db.commit()
    if os.path.isfile(path):
        os.remove(path)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
