"""Main FastAPI application for CFG proxy processing."""

import logging

import httpx
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import Response

from .config import settings
from .utils import IPProcessor, TemplateProcessor

# Configure logging
logging.basicConfig(
    level=getattr(logging, settings.log_level.upper()),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="CFG App",
    description="Python application for proxy rule processing and NETSET expansion",
    version="0.1.0"
)


@app.on_event("startup")
async def startup_event():
    """Initialize application on startup."""
    logger.info("CFG App starting up...")
    logger.info(f"API Host: {settings.api_host}")
    logger.info(f"Alt Host: {settings.alt_host}")
    logger.info(f"IPv4 Block Prefix: /{settings.ipv4_block_prefix}")
    logger.info(f"IPv6 Block Prefix: /{settings.ipv6_block_prefix}")


@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown."""
    logger.info("CFG App shutting down...")


async def forward_request(request: Request, path_with_search: str) -> httpx.Response:
    """Forward request to origin API."""
    target = f"https://{settings.api_host}{path_with_search}"
    logger.info(f"Forwarding to origin: {target}")

    # Prepare headers
    headers = dict(request.headers)
    headers.pop('cookie', None)  # Remove cookies
    headers.pop('host', None)    # Remove host header

    async with httpx.AsyncClient() as client:
        response = await client.get(
            target,
            headers=headers,
            timeout=30.0
        )
        return response


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "version": "0.1.0"}


@app.get("/{path:path}")
async def proxy_handler(request: Request, path: str):
    """Main proxy handler that mimics the Cloudflare Worker behavior."""
    try:
        url = request.url
        path_with_params = url.path + ('?' + url.query if url.query else '')

        logger.info(f"Incoming: {url}")

        # First, try to forward the request to origin
        try:
            response = await forward_request(request, path_with_params)
            logger.info(f"Origin status: {response.status_code}")

            # If not 404, return the response as-is
            if response.status_code != 404:
                return Response(
                    content=response.content,
                    status_code=response.status_code,
                    headers=dict(response.headers)
                )
        except Exception as e:
            logger.error(f"Forward request failed: {e}")
            raise HTTPException(status_code=500, detail="Forward request failed")

        # If we get here, origin returned 404, try template
        tpl_path = url.path + ".tpl" + ('?' + url.query if url.query else '')
        logger.info(f"404 -> try template: {tpl_path}")

        try:
            tpl_response = await forward_request(request, tpl_path)
            if not tpl_response.is_success:
                logger.error(f"Template fetch failed: {tpl_response.status_code}")
                # Return original 404 response
                return Response(
                    content=response.content,
                    status_code=response.status_code,
                    headers=dict(response.headers)
                )
        except Exception as e:
            logger.error(f"Template fetch failed: {e}")
            # Return original 404 response
            return Response(
                content=response.content,
                status_code=response.status_code,
                headers=dict(response.headers)
            )

        # Process template
        tpl_text = tpl_response.text

        # Create IP processor and template processor
        ip_processor = IPProcessor(
            ipv4_block_prefix=settings.ipv4_block_prefix,
            ipv6_block_prefix=settings.ipv6_block_prefix
        )
        template_processor = TemplateProcessor(ip_processor)

        # Process the template
        final_body = await template_processor.process_template(tpl_text)

        return Response(
            content=final_body,
            status_code=200,
            headers={"content-type": "text/plain; charset=utf-8"}
        )

    except Exception as e:
        logger.error(f"Worker error: {str(e)}")
        return Response(
            content="Worker error",
            status_code=500,
            headers={"content-type": "text/plain; charset=utf-8"}
        )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "src.main:app",
        host=settings.host,
        port=settings.port,
        reload=True
    )
