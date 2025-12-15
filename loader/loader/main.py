def main():
    from loader.api import API
    from loader.config import Config
    from loader.service import Loader

    config = Config()
    loader = Loader(
        db_uri=config.postgres.uri(),
        csv_path=config.loader.csv_path.as_posix(),
    )
    api = API(loader)
    api.serve_http(config.host, config.port)


if __name__ == "__main__":
    main()
