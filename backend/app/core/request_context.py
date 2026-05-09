from contextvars import ContextVar
from typing import Optional

trace_id_ctx_var: ContextVar[Optional[str]] = ContextVar("trace_id", default=None)


def get_trace_id() -> Optional[str]:
    return trace_id_ctx_var.get()
