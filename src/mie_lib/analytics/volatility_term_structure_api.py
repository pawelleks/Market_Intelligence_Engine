
from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse
from mie_lib.analytics.volatility_term_structure import generate_term_structure_report

router = APIRouter()

@router.get("/api/v1/analytics/volatility/term-structure")
def get_volatility_term_structure() -> JSONResponse:
    """
    Returns data for the Volatility Term Structure page.
    Serves pre-computed JSON report.
    """
    try:
        report = generate_term_structure_report()
        
        if not report or not report.get("data"):
             raise HTTPException(status_code=404, detail="No volatility data available.")
             
        return JSONResponse(content=report)
        
    except Exception as e:
        print(f"Error serving Volatility Term Structure: {e}")
        raise HTTPException(status_code=500, detail=str(e))
