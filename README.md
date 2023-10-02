# browsertrix-harvester

CLI app for performing a web crawl via [Browsertrix-Crawler](https://github.com/webrecorder/browsertrix-crawler), and optionally parsing structured metadata records from the crawl output [WACZ](https://replayweb.page/docs/wacz-format) file.

## Architecture

See [architecture docs](docs/architecture.md).

## Development

**NOTE**: When performing web crawls, this application invokes browsertrix-crawler.  While theoretically possible to install browsertrix-crawler on your local machine as a callable binary, this application is oriented around running only inside of a Docker container where it is already installed.  For this reason, the pipenv convenience command `harvest-dockerized` has been created.

## Environment Variables

```dotenv
WORKSPACE=None
SENTRY_DSN=None# If set to a valid Sentry DSN, enables Sentry exception monitoring. This is not needed for local development.
```

### Build Application

- To install with dev dependencies: `make install`
- To update dependencies: `make update`
- To run unit tests: `make test`
- To lint the repo: `make lint`
- Install pre-commit hooks: `pipenv run pre-commit install`
- Build docker image: `make dist-local`
  - builds local image `browsertrix-harvester-dev:latest`
- To run the app:
  - Non-Dockerized: `pipenv run harvest --help`
    - works locally for many things, but will throw error for actions that perform crawls
  - Dockerized: `pipenv run harvest-dockerized --help`
    - provides full functionality by running as a docker container
    - host machine `~/.aws` directory mounted into container to provide AWS credentials to container
    - points back to the pipenv command `harvest` 

### Testing and Linting

```shell
make test
make lint
```

#### Local Test Crawl
```shell
make test-harvest-local
```

This Make command kicks off a harvest via a local docker container.  The Make command reflects some ways in which a harvest can be configured, including local or S3 filepath to a configuration YAML, setting an output metadata file, and even passing in miscellaneous browsertrix arguments to the crawler not explicitly defined as CLI parameters in this app.

#### Dev1 Test Crawl

```shell
make test-harvest-ecs
```

This Make command issues an AWS CLI command to start an ECS task running effectively the same harvest as outlined above for local testing, but in the Dev1 environment as a Fargate ECS task.

Looking at the script run, `bin/test-harvest-ecs.sh`, it demonstrates how output files can be S3 URIs.

## CLI commands

### Main
```shell
pipenv run harvest
```

```text
Options:
  -v, --verbose  Pass to log at debug level instead of info
  -h, --help     Show this message and exit.

Commands:
  harvest            Perform a web crawl and parse structured data.
  parse-url-content  Get HTML content for a URL from a WACZ archive file.
  shell              Run a bash shell inside the docker container.
```

### Shell environment
```shell
pipenv run harvest shell
```
```text
Usage: -c shell [OPTIONS]

  Run a bash shell inside the docker container.

Options:
  -h, --help            Show this message and exit.
```