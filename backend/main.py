"""
Hiver Brand AI Support Agent — FastAPI Backend
Brand: Apple Support
Model: llama-3.3-70b-versatile (Groq)
"""

import os
import sys
import json
import time
from pathlib import Path
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from dotenv import load_dotenv

# Load .env
load_dotenv(Path(__file__).resolve().parent / ".env", override=True)

# Add src to path
sys.path.insert(0, str(Path(__file__).resolve().parent))

from src.preprocessing.loader import load_and_process_data
from src.retrieval.index import build_index, get_index
from src.pipeline import run_pipeline
from src.evaluation.golden_set import load_golden_set, get_golden_stats, GOLDEN_EXAMPLES
from src.evaluation.intent_eval import evaluate_intent, compare_baselines
from src.evaluation.retrieval_eval import evaluate_retrieval
from src.evaluation.response_eval import evaluate_responses
from src.evaluation.decision_eval import evaluate_decisions
from src.intent.classifier import classify_intent_llm
from src.intent.baseline import get_majority_baseline, get_tfidf_baseline
from src.retrieval.retriever import retrieve
from src.decision.decision_engine import decide
from src.intent.taxonomy import INTENT_TAXONOMY

# ── Startup ────────────────────────────────────────────────────────────────

conversations_cache = []

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Load data and build index on startup."""
    global conversations_cache
    print("[Startup] Loading Apple Support conversations...")
    try:
        conversations_cache = load_and_process_data()
        print(f"[Startup] Loaded {len(conversations_cache)} conversations.")

        # Build/load index
        print("[Startup] Building TF-IDF index...")
        build_index(conversations_cache)
        print("[Startup] Index ready.")

        # Save golden set to disk
        gs = load_golden_set()
        print(f"[Startup] Golden set ready: {len(gs)} examples.")

        # Train TFIDF baseline if not already trained
        tfidf_baseline = get_tfidf_baseline()
        if tfidf_baseline.model is None:
            print("[Startup] Training TF-IDF baseline...")
            messages = [ex['message'] for ex in gs]
            labels = [ex['intent'] for ex in gs]
            for intent, data in INTENT_TAXONOMY.items():
                messages.append(data['description'])
                labels.append(intent)
                for kw in data['keywords']:
                    messages.append(kw)
                    labels.append(intent)
            tfidf_baseline.train(messages, labels)
            print("[Startup] TF-IDF baseline trained and ready.")
    except Exception as e:
        print(f"[Startup] Error: {e}")
    yield
    print("[Shutdown] Cleaning up...")


app = FastAPI(
    title="Hiver Brand AI Support Agent",
    description="Apple Support RAG Agent with full evaluation harness",
    version="1.0.0",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve frontend
FRONTEND_DIR = Path(__file__).resolve().parent.parent / "frontend"
if FRONTEND_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(FRONTEND_DIR)), name="static")


# ── Request Models ─────────────────────────────────────────────────────────

class ChatRequest(BaseModel):
    message: str
    top_k: int = 5


class EvaluateRequest(BaseModel):
    mode: str = "quick"  # "quick" or "full"
    sample_size: int = 20


# ── Health ─────────────────────────────────────────────────────────────────

@app.get("/api/health")
async def health():
    index = get_index()
    return {
        "status": "ok",
        "brand": "AppleSupport",
        "model": os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile"),
        "conversations_loaded": len(conversations_cache),
        "index_built": index is not None,
        "groq_configured": bool(os.getenv("GROQ_API_KEY")),
        "timestamp": time.time()
    }


# ── Chat (Full Pipeline) ───────────────────────────────────────────────────

@app.post("/api/chat")
async def chat(request: ChatRequest):
    """Run the full support pipeline for a customer message."""
    if not request.message.strip():
        raise HTTPException(status_code=400, detail="Message cannot be empty")

    if get_index() is None:
        raise HTTPException(status_code=503, detail="Index not ready yet. Please wait.")

    try:
        result = run_pipeline(
            customer_message=request.message.strip(),
            top_k=request.top_k
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── Pipeline Trace (Step-by-Step) ──────────────────────────────────────────

@app.post("/api/pipeline/trace")
async def pipeline_trace(request: ChatRequest):
    """Same as /api/chat but returns detailed trace for display."""
    return await chat(request)


# ── Taxonomy ───────────────────────────────────────────────────────────────

@app.get("/api/taxonomy")
async def get_taxonomy():
    """Return the intent taxonomy."""
    return {
        "brand": "AppleSupport",
        "intents": INTENT_TAXONOMY,
        "total_intents": len(INTENT_TAXONOMY)
    }


# ── Golden Set ─────────────────────────────────────────────────────────────

@app.get("/api/golden-set")
async def golden_set_info():
    """Return golden set statistics."""
    stats = get_golden_stats()
    return {
        "stats": stats,
        "examples": GOLDEN_EXAMPLES
    }


# ── Evaluation ─────────────────────────────────────────────────────────────

@app.post("/api/evaluate")
async def evaluate(request: EvaluateRequest):
    """
    Run the full evaluation harness on the golden set.
    
    mode: "quick" = intent + decision only (no LLM calls)
          "full"  = all metrics including LLM judge (slower)
    """
    if get_index() is None:
        raise HTTPException(status_code=503, detail="Index not ready yet.")

    golden = load_golden_set()
    sample = golden[:request.sample_size] if request.mode == "quick" else golden
    n = len(sample)

    print(f"[Evaluate] Running {request.mode} evaluation on {n} examples...")

    # ── Step 1: Run pipeline for each example ──────────────────────────────
    pipeline_outputs = []
    intent_predictions = []
    retrieval_results = []
    decision_outputs = []

    for i, ex in enumerate(sample):
        print(f"[Evaluate] Example {i+1}/{n}: {ex['id']}")
        try:
            # Exclude the current example's ID from retrieval (prevent eval leakage)
            output = run_pipeline(
                customer_message=ex["message"],
                top_k=5,
                exclude_ids={ex["id"]}
            )
            pipeline_outputs.append(output)
            intent_predictions.append(output["intent"])
            retrieval_results.append(output["retrieval"])
            decision_outputs.append(output["decision"])
        except Exception as e:
            print(f"[Evaluate] Error on {ex['id']}: {e}")
            # Add fallback output
            pipeline_outputs.append({"intent": {"intent": "general_question", "confidence": 0.5}, "retrieval": {"results": [], "retrieval_confidence": 0, "evidence_quality": "weak", "top_similarity": 0, "avg_similarity": 0, "num_results": 0}, "generated_response": {"reply": "", "evidence_used": [], "method": "error"}, "decision": {"decision": "ESCALATE", "reason": "Pipeline error", "risk_level": "HIGH"}})
            intent_predictions.append({"intent": "general_question", "confidence": 0.5, "method": "error"})
            retrieval_results.append({"results": [], "retrieval_confidence": 0, "evidence_quality": "weak", "top_similarity": 0, "avg_similarity": 0, "num_results": 0})
            decision_outputs.append({"decision": "ESCALATE", "reason": "Error", "risk_level": "HIGH"})

    # ── Step 2: Baseline predictions ──────────────────────────────────────
    print("[Evaluate] Running baseline predictions...")
    majority_baseline = get_majority_baseline()
    tfidf_baseline = get_tfidf_baseline()
    majority_preds = majority_baseline.predict_batch([ex["message"] for ex in sample])
    tfidf_preds = tfidf_baseline.predict_batch([ex["message"] for ex in sample])

    # ── Step 3: Intent Evaluation ──────────────────────────────────────────
    print("[Evaluate] Computing intent metrics...")
    intent_metrics = evaluate_intent(intent_predictions, sample)
    baseline_comparison = compare_baselines(
        llm_predictions=intent_predictions,
        majority_predictions=majority_preds,
        tfidf_predictions=tfidf_preds,
        golden_examples=sample
    )

    # ── Step 4: Retrieval Evaluation ───────────────────────────────────────
    print("[Evaluate] Computing retrieval metrics...")
    retrieval_metrics = evaluate_retrieval(retrieval_results, sample)

    # ── Step 5: Decision Evaluation ────────────────────────────────────────
    print("[Evaluate] Computing decision metrics...")
    decision_metrics = evaluate_decisions(decision_outputs, sample)

    # ── Step 6: Response Evaluation (LLM Judge) — only in full mode ────────
    response_metrics = None
    if request.mode == "full":
        print("[Evaluate] Running LLM-as-judge (this may take a moment)...")
        response_metrics = evaluate_responses(pipeline_outputs, sample)

    print("[Evaluate] Evaluation complete.")

    return {
        "mode": request.mode,
        "sample_size": n,
        "intent_metrics": intent_metrics,
        "baseline_comparison": baseline_comparison,
        "retrieval_metrics": retrieval_metrics,
        "decision_metrics": decision_metrics,
        "response_metrics": response_metrics,
        "pipeline_outputs": [
            {
                "id": ex["id"],
                "message": ex["message"],
                "true_intent": ex["intent"],
                "intent": pipeline_outputs[i]["intent"],
                "decision": pipeline_outputs[i]["decision"]["decision"],
                "expected_decision": ex["expected_decision"],
                "reply": pipeline_outputs[i].get("final_reply", "")[:200]
            }
            for i, ex in enumerate(sample)
        ]
    }


# ── Frontend ───────────────────────────────────────────────────────────────

@app.get("/")
async def serve_frontend():
    index_file = FRONTEND_DIR / "index.html"
    if index_file.exists():
        return FileResponse(str(index_file))
    return {"message": "Frontend not found. Serve frontend/index.html separately."}


@app.get("/style.css")
async def serve_css():
    css_file = FRONTEND_DIR / "style.css"
    if css_file.exists():
        return FileResponse(str(css_file), media_type="text/css")
    raise HTTPException(status_code=404, detail="style.css not found")


@app.get("/app.js")
async def serve_js():
    js_file = FRONTEND_DIR / "app.js"
    if js_file.exists():
        return FileResponse(str(js_file), media_type="application/javascript")
    raise HTTPException(status_code=404, detail="app.js not found")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=False)
