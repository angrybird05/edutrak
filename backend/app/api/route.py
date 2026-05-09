import json
from typing import Callable

from fastapi import Request, Response
from fastapi.routing import APIRoute
from fastapi.responses import JSONResponse
from starlette.responses import StreamingResponse


class StandardizedResponseRoute(APIRoute):
    """
    Custom API Route that intercepts successful JSON responses and wraps them
    in a standardized enterprise envelope: { success: true, data: ..., error: null }
    """
    def get_route_handler(self) -> Callable:
        original_route_handler = super().get_route_handler()

        async def custom_route_handler(request: Request) -> Response:
            response: Response = await original_route_handler(request)

            # Skip streaming responses, file downloads, or pre-wrapped errors
            if isinstance(response, StreamingResponse):
                return response
                
            content_type = response.headers.get("content-type", "")
            if "application/json" not in content_type:
                return response

            # Status codes 400+ are handled by the global exception handlers in middleware.py
            if response.status_code >= 400:
                return response

            try:
                if hasattr(response, "body"):
                    data = json.loads(response.body.decode("utf-8"))
                    
                    # Prevent double wrapping if endpoints are already compliant
                    if isinstance(data, dict) and "success" in data and "data" in data:
                        return response
                        
                    wrapped_content = {
                        "success": True,
                        "data": data,
                        "error": None
                    }
                    
                    # Create a fresh JSONResponse to recalculate Content-Length
                    new_response = JSONResponse(
                        content=wrapped_content,
                        status_code=response.status_code,
                    )
                    
                    # Copy over cache-control or other custom headers (excluding content-length/type)
                    for key, value in response.headers.items():
                        if key.lower() not in ["content-length", "content-type"]:
                            new_response.headers[key] = value
                            
                    return new_response
            except Exception:
                # Fallback to original response on parsing errors
                pass

            return response

        return custom_route_handler
