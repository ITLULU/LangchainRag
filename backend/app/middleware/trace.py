"""Trace ID 中间件——为每个请求注入 trace_id"""
import uuid
import time
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request


class TraceMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        trace_id = request.headers.get("X-Trace-Id", str(uuid.uuid4()))
        request.state.trace_id = trace_id
        request.state.start_time = time.time()

        response = await call_next(request)

        response.headers["X-Trace-Id"] = trace_id
        response.headers["X-Process-Time"] = f"{time.time() - request.state.start_time:.3f}s"
        return response