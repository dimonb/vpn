"""Main FastAPI application for CFG proxy processing."""

import logging
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import Response

from .auth import extract_template_tags, require_auth
from .clash_processor import ClashProcessor
from .config import settings
from .processor import TemplateProcessor

# Configure logging
logging.basicConfig(
    level=getattr(logging, settings.log_level.upper()),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan event handler for startup and shutdown."""
    # Startup
    logger.info("CFG App starting up...")
    logger.info(f"Config Host: {settings.config_host}")
    logger.info(f"IPv4 Block Prefix: /{settings.ipv4_block_prefix}")
    logger.info(f"IPv6 Block Prefix: /{settings.ipv6_block_prefix}")
    
    yield
    
    # Shutdown
    logger.info("CFG App shutting down...")


app = FastAPI(
    title="CFG App",
    description="Python application for proxy rule processing and NETSET expansion",
    version="0.1.0",
    lifespan=lifespan
)


async def forward_request(request: Request, path_with_search: str) -> httpx.Response:
    """Forward request to origin API."""
    target = f"https://{settings.config_host}{path_with_search}"
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
            raise HTTPException(status_code=500, detail="Forward request failed") from e

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

        # Extract template tags
        tags = extract_template_tags(tpl_text)
        logger.info(f"Template tags: {tags}")

        # Check authentication if AUTH tag is present
        if 'AUTH' in tags:
            require_auth(request)

        # Create HTTP client for template processor
        async with httpx.AsyncClient() as http_client:
            # Create template processor
            template_processor = TemplateProcessor(http_client)

            # Process based on template type
            if 'CLASH' in tags:
                # Process as CLASH YAML
                clash_processor = ClashProcessor(template_processor)
                final_body = await clash_processor.process_clash_config(
                    tpl_text,
                    request.headers.get('host', ''),
                    dict(request.headers)
                )
            else:
                # Process as regular template (SHADOWROCKET or default)
                final_body = await template_processor.process_template(
                    tpl_text,
                    request.headers.get('host', ''),
                    dict(request.headers)
                )

            return Response(
                content=final_body,
                status_code=200,
                headers={"content-type": "text/plain; charset=utf-8"}
            )

    except HTTPException:
        # Re-raise HTTP exceptions (like 401 Authentication required)
        raise
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
