def main():
    from etl.api import API
    from etl.config import Config
    from etl.service import ETLPipeline

    config = Config()
    pipeline = ETLPipeline(
        raw_db_uri=config.raw_db.uri(),
        analytics_db_uri=config.analytics_db.uri(),
        taxi_zones_file=config.pipeline.taxi_zones_file.as_posix(),
    )
    api = API(pipeline)
    api.serve_http(config.host, config.port)


if __name__ == "__main__":
    main()
