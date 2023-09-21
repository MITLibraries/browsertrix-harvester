# browsertrix-harvester

CLI app for performing a web crawl via [Browsertrix-Crawler](https://github.com/webrecorder/browsertrix-crawler), and optionally parsing structured metadata records from the crawl output [WACZ](https://replayweb.page/docs/wacz-format) file.

## Development

**NOTE**: When performing web crawls, this application invokes browsertrix-crawler.  While theoretically possible to install browsertrix-crawler on your local machine as a callable binary, this application is oriented around running only inside of a Docker container where it is already installed.  For this reason, the pipenv convenience command `btrixharvest-dockerized` has been created (more on this below).

### Build Application

- To install with dev dependencies: `make install`
- To update dependencies: `make update`
- To run unit tests: `make test`
- To lint the repo: `make lint`
- Build docker image: `make build-docker`
  - builds local image `browsertrix-harvester-dev:latest`
- To run the app:
  - Non-Dockerized: `pipenv run btrixharvest --help`
    - works locally for many things, but will throw error for actions that perform crawls
  - Dockerized: `pipenv run btrixharvest-dockerized --help`
    - full functionality locally
    - invokes docker container, with an entrypoint that points back to `btrixharvest` 

## Environment Variables

```dotenv
WORKSPACE=None
SENTRY_DSN=None# If set to a valid Sentry DSN, enables Sentry exception monitoring. This is not needed for local development.
```
