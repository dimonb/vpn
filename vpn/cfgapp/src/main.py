"""Main FastAPI application for CFG proxy processing."""

import logging
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, Response
from fastapi.templating import Jinja2Templates
from fastapi.exceptions import HTTPException as FastAPIHTTPException
from starlette.exceptions import HTTPException as StarletteHTTPException

from .auth import extract_template_tags, require_auth
from .clash_processor import ClashProcessor
from .config import settings
from .processor import TemplateProcessor
from .proxy_config import ProxyConfig

# Configure logging
logging.basicConfig(
    level=getattr(logging, settings.log_level.upper()),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Global proxy config instance
proxy_config: ProxyConfig | None = None

# Templates
templates = Jinja2Templates(directory="templates")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan event handler for startup and shutdown."""
    global proxy_config

    # Startup
    logger.info("CFG App starting up...")
    logger.info(f"Config Host: {settings.config_host}")
    logger.info(f"IPv4 Block Prefix: /{settings.ipv4_block_prefix}")
    logger.info(f"IPv6 Block Prefix: /{settings.ipv6_block_prefix}")

    # Initialize proxy config if path is provided
    if settings.proxy_config:
        try:
            proxy_config = ProxyConfig(settings.proxy_config)
            logger.info(f"Proxy config initialized from: {settings.proxy_config}")
        except Exception as e:
            logger.error(f"Failed to initialize proxy config: {e}")
            proxy_config = None
    else:
        logger.info("No proxy config path provided, proxy features disabled")

    yield

    # Shutdown
    logger.info("CFG App shutting down...")


app = FastAPI(
    title="CFG App",
    description="Python application for proxy rule processing and NETSET expansion",
    version="0.1.0",
    lifespan=lifespan,
)

@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    """Handle HTTP exceptions including 404 errors."""
    if exc.status_code == 404:
        logger.info(f"404 Not Found: {request.url.path}")
        return Response(
            content="Path not found",
            status_code=404,
            headers={"content-type": "text/plain; charset=utf-8"},
        )
    return Response(
        content=exc.detail,
        status_code=exc.status_code,
        headers={"content-type": "text/plain; charset=utf-8"},
    )

@app.exception_handler(FastAPIHTTPException)
async def fastapi_http_exception_handler(request: Request, exc: FastAPIHTTPException):
    """Handle FastAPI HTTP exceptions."""
    logger.info(f"FastAPI HTTP Exception: {exc.status_code} - {exc.detail}")
    return Response(
        content=exc.detail,
        status_code=exc.status_code,
        headers={"content-type": "text/plain; charset=utf-8"},
    )


async def forward_request(request: Request, path_with_search: str) -> httpx.Response:
    """Forward request to origin API."""
    target = f"https://{settings.config_host}{path_with_search}"
    logger.info(f"Forwarding to origin: {target}")

    # Prepare headers
    headers = dict(request.headers)
    headers.pop("cookie", None)  # Remove cookies
    headers.pop("host", None)  # Remove host header

    async with httpx.AsyncClient() as client:
        response = await client.get(target, headers=headers, timeout=30.0)
        return response


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "version": "0.1.0"}


@app.get("/sr")
async def shadowrocket_subscription(request: Request):
    """ShadowRocket subscription endpoint."""
    try:
        # Check if proxy config is available
        if not proxy_config:
            raise HTTPException(
                status_code=500, detail="Proxy configuration not available"
            )

        # Require authentication
        require_auth(request, proxy_config)

        # Extract subscription and password from query parameters
        query_params = dict(request.query_params)
        sub_name = query_params.get("sub")
        password = query_params.get("hash")
        user = query_params.get("u")

        # Generate ShadowRocket subscription
        subscription_b64 = proxy_config.generate_shadowrocket_subscription(
            sub_name, password, user
        )

        return Response(
            content=subscription_b64,
            status_code=200,
            headers={"content-type": "text/plain; charset=utf-8"},
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error generating ShadowRocket subscription: {e}")
        raise HTTPException(status_code=500, detail="Internal server error") from e


@app.get("/sub", response_class=HTMLResponse)
async def subscription_page(request: Request):
    """Subscription page with QR code and copy button."""
    try:
        # Check if proxy config is available
        if not proxy_config:
            raise HTTPException(
                status_code=500, detail="Proxy configuration not available"
            )

        # Require authentication
        require_auth(request, proxy_config)

        # Extract subscription and password from query parameters
        query_params = dict(request.query_params)
        sub_name = query_params.get("sub")
        password = query_params.get("hash")
        user = query_params.get("u")

        # Get base URL from settings or fallback to request
        base_url = settings.base_url
        if not base_url:
            base_url = (
                f"{request.url.scheme}://{request.headers.get('host', 'localhost')}"
            )

        # Generate subscription URL
        subscription_url = proxy_config.generate_subscription_url(
            base_url, user, sub_name, password
        )

        # Generate QR code
        qr_code_b64 = proxy_config.generate_qr_code(subscription_url)

        # Render template
        return templates.TemplateResponse(
            request,
            "subscription.html",
            {
                "subscription_url": subscription_url,
                "qr_code": qr_code_b64,
                "user": user,
                "subscription": sub_name or "default",
            },
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error generating subscription page: {e}")
        raise HTTPException(status_code=500, detail="Internal server error") from e


@app.get("/{path:path}")
async def proxy_handler(request: Request, path: str):
    """Main proxy handler that mimics the Cloudflare Worker behavior."""
    try:
        url = request.url
        path_with_params = url.path + ("?" + url.query if url.query else "")

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
                    headers=dict(response.headers),
                )
        except Exception as e:
            logger.error(f"Forward request failed: {e}")
            raise HTTPException(status_code=500, detail="Forward request failed") from e

        # If we get here, origin returned 404, try template
        tpl_path = url.path + ".tpl" + ("?" + url.query if url.query else "")
        logger.info(f"Origin returned 404 for {url.path}, trying template: {tpl_path}")

        try:
            tpl_response = await forward_request(request, tpl_path)
            if not tpl_response.is_success:
                logger.info(f"Template not found for path: {url.path} (status: {tpl_response.status_code})")
                # Return simple 404 response, Caddy will handle the HTML
                return Response(
                    content="Not Found",
                    status_code=404,
                    headers={"content-type": "text/plain; charset=utf-8"},
                )
        except Exception as e:
            logger.info(f"Template fetch failed for path: {url.path} - {e}")
            # Return simple 404 response, Caddy will handle the HTML
            return Response(
                content="Not Found",
                status_code=404,
                headers={"content-type": "text/plain; charset=utf-8"},
            )

        # Process template
        tpl_text = tpl_response.text

        # Extract template tags
        tags = extract_template_tags(tpl_text)
        logger.info(f"Template tags: {tags}")

        # Check authentication if AUTH tag is present
        if "AUTH" in tags:
            require_auth(request, proxy_config)

        # Create HTTP client for template processor
        async with httpx.AsyncClient() as http_client:
            # Create template processor
            template_processor = TemplateProcessor(http_client)

            # Prepare headers with query string for proxy config
            request_headers = dict(request.headers)
            if url.query:
                request_headers["x-query-string"] = url.query

            # Process based on template type
            if "CLASH" in tags:
                # Process as CLASH YAML
                clash_processor = ClashProcessor(template_processor, proxy_config)
                final_body = await clash_processor.process_clash_config(
                    tpl_text, request.headers.get("host", ""), request_headers
                )
            else:
                # Process as regular template (SHADOWROCKET or default)
                final_body = await template_processor.process_template(
                    tpl_text, request.headers.get("host", ""), request_headers
                )

            return Response(
                content=final_body,
                status_code=200,
                headers={"content-type": "text/plain; charset=utf-8"},
            )

    except HTTPException:
        # Re-raise HTTP exceptions (like 401 Authentication required)
        raise
    except Exception as e:
        logger.error(f"Worker error: {str(e)}")
        return Response(
            content="Worker error",
            status_code=500,
            headers={"content-type": "text/plain; charset=utf-8"},
        )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("src.main:app", host=settings.host, port=settings.port, reload=True)
