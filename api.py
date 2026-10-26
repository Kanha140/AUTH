import asyncio
import logging
from aiohttp import web
import database
import webhook_logger
import db_sync
from config import API_HOST, API_PORT

logger = logging.getLogger("AuthAPI")

routes = web.RouteTableDef()

@routes.get("/")
async def root_handler(request: web.Request):
    return web.json_response({
        "system": "Axenor Auth Server",
        "status": "online",
        "version": "1.0.0"
    })

@routes.get("/api/status")
async def status_handler(request: web.Request):
    return web.json_response({"status": "running"})

@routes.post("/api/login")
async def login_post(request: web.Request):
    try:
        data = await request.json()
    except Exception:
        try:
            data = await request.post()
        except Exception:
            data = {}

    username = data.get("username", "")
    password = data.get("password", "")
    hwid = data.get("hwid", "")

    client_ip = request.headers.get("X-Forwarded-For", request.remote or "Unknown")

    result = database.authenticate_client(username, password, hwid)
    status_code = 200 if result["success"] else 400
    if result.get("status") in ["USER_NOT_FOUND", "WRONG_PASSWORD"]:
        status_code = 401
    elif result.get("status") in ["HWID_MISMATCH", "EXPIRED"]:
        status_code = 403

    # Send log to webhook asynchronously
    asyncio.create_task(
        webhook_logger.log_client_login(
            username=username,
            status=result.get("status", "UNKNOWN"),
            message=result.get("message", ""),
            hwid=hwid,
            ip=client_ip
        )
    )

    if result.get("status") == "HWID_BOUND_SUCCESS":
        db_sync.trigger_cloud_backup()

    return web.json_response(result, status=status_code)

@routes.get("/api/login")
async def login_get(request: web.Request):
    username = request.query.get("username", "")
    password = request.query.get("password", "")
    hwid = request.query.get("hwid", "")

    client_ip = request.headers.get("X-Forwarded-For", request.remote or "Unknown")

    result = database.authenticate_client(username, password, hwid)
    status_code = 200 if result["success"] else 400
    if result.get("status") in ["USER_NOT_FOUND", "WRONG_PASSWORD"]:
        status_code = 401
    elif result.get("status") in ["HWID_MISMATCH", "EXPIRED"]:
        status_code = 403

    # Send log to webhook asynchronously
    asyncio.create_task(
        webhook_logger.log_client_login(
            username=username,
            status=result.get("status", "UNKNOWN"),
            message=result.get("message", ""),
            hwid=hwid,
            ip=client_ip
        )
    )

    if result.get("status") == "HWID_BOUND_SUCCESS":
        db_sync.trigger_cloud_backup()

    return web.json_response(result, status=status_code)

def create_app() -> web.Application:
    app = web.Application()
    app.add_routes(routes)
    return app

async def start_api_server(host: str = API_HOST, port: int = API_PORT):
    app = create_app()
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, host, port)
    await site.start()
    logger.info(f"Auth REST API listening on http://{host}:{port}")
    return runner
