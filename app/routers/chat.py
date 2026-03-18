from fastapi import APIRouter, HTTPException, Request

from app.agents.orchestrator_agent import OrchestratorAgent

router = APIRouter()

_orchestrator = OrchestratorAgent()


@router.post("/chat")
async def chat_endpoint(request: Request):
    """Receive a natural language message and return an agent-generated response."""
    data = await request.json()
    user_message = data.get("message", "").strip()
    if not user_message:
        raise HTTPException(status_code=400, detail="Message is required")

    try:
        result = await _orchestrator.route(user_message)
        return {
            "response": result.get("response", ""),
            "stock":    result.get("stock"),
            "stocks":   result.get("stocks"),
            "options":  result.get("options"),
            "news":     result.get("news"),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
