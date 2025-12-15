from fastapi import FastAPI, Request, status
from fastapi.responses import PlainTextResponse

from loader.service import Loader


class API:
    def __init__(self, loader: Loader):
        self.loader = loader

    def _asgi(self) -> FastAPI:
        app = FastAPI(title="Loader", summary="Load raw CSV data into database")

        @app.exception_handler(Exception)
        async def handle_exception(request: Request, exc: Exception):  # type: ignore
            return PlainTextResponse(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, content=str(exc)
            )

        @app.post("/load-csv", summary="Load CSV data into database")
        async def load(start: int = 0, stop: int = 100):  # type: ignore
            loaded_rows_count = await self.loader.load_csv(start, stop)
            return PlainTextResponse(
                status_code=status.HTTP_200_OK,
                content=f"loaded {loaded_rows_count} new rows",
            )

        @app.post(
            "/init-db", summary="Initialize database (create tables, fill constants)"
        )
        async def init_db():  # type: ignore
            await self.loader.init()
            return PlainTextResponse(
                status_code=status.HTTP_200_OK,
                content="tables created",
            )

        return app

    def serve_http(self, host: str = "127.0.0.1", port: int = 80):
        import uvicorn

        uvicorn.run(self._asgi(), host=host, port=port)
