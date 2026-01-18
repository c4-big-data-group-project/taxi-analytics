from datetime import datetime

from fastapi import FastAPI, Request, status
from fastapi.responses import PlainTextResponse

from etl.service import ETLPipeline


class API:
    def __init__(self, pipeline: ETLPipeline):
        self.pipeline = pipeline

    def _asgi(self) -> FastAPI:
        app = FastAPI(
            title="ETL Pipeline",
            summary="Processes raw data to form a more structured data",
        )

        @app.exception_handler(Exception)
        async def handle_exception(request: Request, exc: Exception):  # type: ignore
            return PlainTextResponse(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, content=str(exc)
            )

        @app.post(
            "/pipe",
            summary="Processes raw data from raw db and save the results in analytics db",
        )
        async def pipe(since: datetime) -> datetime:  # type: ignore
            return self.pipeline.pipe(since)

        @app.post(
            "/init-dbs", summary="Initialize databases on both raw and analytics dbs"
        )
        async def init_dbs():  # type: ignore
            self.pipeline.init()
            return PlainTextResponse(
                status_code=status.HTTP_200_OK,
                content="tables created",
            )

        return app

    def serve_http(self, host: str = "127.0.0.1", port: int = 80):
        import uvicorn

        uvicorn.run(self._asgi(), host=host, port=port)
