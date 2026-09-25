"""FastAPI composition root. All application data stays in HOTEL_DATA_DIR."""

import os
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Annotated
from uuid import UUID

from fastapi import FastAPI, Header, Request, Response
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import ValidationError
from starlette.middleware.trustedhost import TrustedHostMiddleware

from .adapters import PMSimulator, RecipientSimulator, ServiceUnavailable
from .db import Database
from .interpreter import Interpreter, RuleInterpreter
from .models import (
    ITEMS,
    AdvanceInput,
    DomainError,
    Interpretation,
    InterpretInput,
    ModeInput,
    OrderInput,
    ServiceName,
)
from .service import HotelService

ROOT = Path(__file__).resolve().parent.parent


def create_app(data_dir: Path | None = None, interpreter: Interpreter | None = None) -> FastAPI:
    directory = data_dir or Path(os.environ.get("HOTEL_DATA_DIR", str(ROOT / "data")))

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        pms = PMSimulator()
        simulator = RecipientSimulator(Database(directory / "recipients.sqlite"))
        app.state.pms = pms
        app.state.simulator = simulator
        app.state.service = HotelService(Database(directory / "hotel.sqlite"), pms, simulator)
        app.state.interpreter = interpreter or RuleInterpreter()
        yield

    app = FastAPI(
        title="Staydesk · Hotelservice-Demo",
        version="1.0.0",
        lifespan=lifespan,
        docs_url=None,
        redoc_url=None,
    )
    app.add_middleware(
        TrustedHostMiddleware, allowed_hosts=["localhost", "127.0.0.1", "testserver"]
    )

    @app.middleware("http")
    async def local_demo_guard(request: Request, call_next):
        if request.method not in {"GET", "HEAD", "OPTIONS"}:
            origin = request.headers.get("origin")
            if origin and origin != str(request.base_url).rstrip("/"):
                return JSONResponse({"detail": {"message": "Fremder Ursprung abgewiesen."}}, 403)
            if request.headers.get("content-type", "").split(";")[0] != "application/json":
                return JSONResponse({"detail": {"message": "JSON-Anfrage erforderlich."}}, 415)
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; script-src 'self'; style-src 'self'; "
            "img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; "
            "base-uri 'self'; form-action 'self'"
        )
        response.headers["Cache-Control"] = "no-store"
        return response

    @app.exception_handler(DomainError)
    async def domain_error(_request, error):
        return JSONResponse({"detail": error.detail}, status_code=error.status)

    @app.exception_handler(ServiceUnavailable)
    async def service_unavailable(_request, error):
        return JSONResponse({"detail": {"message": str(error)}}, status_code=503)

    @app.get("/api/health")
    def health():
        return {"status": "ok", "app": "staydesk", "version": "1.0.0", "simulation": True}

    @app.get("/api/bootstrap")
    def bootstrap(request: Request):
        return {
            "stays": request.app.state.pms.stays(),
            "items": ITEMS,
            "modes": request.app.state.simulator.modes(),
        }

    @app.post("/api/interpret")
    def interpret(payload: InterpretInput, request: Request):
        request.app.state.pms.require_active(payload.stay_id)
        # Validate every adapter result. A future LLM must use this exact contract too.
        raw = request.app.state.interpreter.interpret(payload.text)
        try:
            result = Interpretation.model_validate(
                raw.model_dump() if isinstance(raw, Interpretation) else raw
            )
        except ValidationError as error:
            raise DomainError(
                502, "invalid_interpretation", "Textadapter liefert kein gültiges Ergebnis."
            ) from error
        if not result.items and not result.questions:
            result.questions.append("Bitte Artikel und Menge nennen, z. B. zwei Handtücher.")
        conflicts = request.app.state.service.conflicts(
            payload.stay_id, {item.kind for item in result.items}
        )
        return {
            **result.model_dump(),
            "ready": bool(result.items) and not result.questions,
            "conflicts": conflicts,
        }

    @app.post("/api/requests")
    def submit(
        payload: OrderInput,
        request: Request,
        response: Response,
        idempotency_key: Annotated[UUID, Header()],
    ):
        result = request.app.state.service.submit(payload, str(idempotency_key))
        response.status_code = 200 if result["replayed"] else 201
        return result

    @app.get("/api/orders")
    def orders(request: Request, stay_id: str | None = None):
        if stay_id is not None:
            request.app.state.pms.require_active(stay_id)
        return {"orders": request.app.state.service.orders(stay_id=stay_id)}

    @app.post("/api/orders/{order_id}/reconcile")
    def reconcile(order_id: UUID, request: Request):
        return request.app.state.service.reconcile(str(order_id))

    @app.post("/api/simulator/{service}/mode")
    def set_mode(service: ServiceName, payload: ModeInput, request: Request):
        request.app.state.simulator.set_mode(service, payload.mode)
        return {"modes": request.app.state.simulator.modes()}

    @app.get("/api/simulator/receipts")
    def receipts(request: Request):
        return {"receipts": request.app.state.simulator.receipts()}

    @app.post("/api/simulator/orders/{order_id}/advance")
    def advance(order_id: UUID, payload: AdvanceInput, request: Request):
        request.app.state.service.get_order(str(order_id))
        request.app.state.simulator.advance(str(order_id), payload.status)
        return request.app.state.service.reconcile(str(order_id))

    @app.get("/")
    def index():
        return FileResponse(ROOT / "app" / "static" / "index.html")

    app.mount("/static", StaticFiles(directory=ROOT / "app" / "static"), name="static")
    return app


app = create_app()
