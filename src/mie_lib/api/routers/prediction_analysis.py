from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from pathlib import Path

router = APIRouter()

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent.parent
ANALYSIS_DIR = PROJECT_ROOT / "data" / "analysis"

@router.get("/analysis/prediction/dashboard")
async def get_model_comparison():
    """Serve the model comparison dashboard JSON file"""
    file_path = ANALYSIS_DIR / "dashboard" / "model_comparison.json"
    
    if not file_path.exists():
        raise HTTPException(
            status_code=404,
            detail="Model comparison data not found. Run analysis scripts to generate."
        )
    
    return FileResponse(str(file_path), media_type="application/json")
