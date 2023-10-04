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

### Perform web crawl and harvest data
This is the primary command for this application.  This performs a web crawl, then optionally parses the results of that crawl into structured data and writes to a specific location.

See section [Browsertrix Crawl Configuration](#browsertrix-crawl-configuration) for details about configuring the browsertrix crawl part of a harvest.

**NOTE:** if neither `--wacz-output-file` or `--metadata-output-file` is set, a crawl will be performed, but nothing will exist outside of the container after it completes.

```shell
# run harvest as local docker container
pipenv run harvest-dockerized harvest

# command used for deployed ECS task
pipenv run harvest harvest
```
```text
Usage: -c harvest [OPTIONS]

  Perform a web crawl and parse structured data.

Options:
  --config-yaml-file TEXT   Filepath of browsertrix config YAML. Can be a
                            local filepath or an S3 URI, e.g.
                            s3://bucketname/crawl-config.yaml  [required]
  --crawl-name TEXT         Optional override for crawl name. [Default
                            'crawl-<TIMESTAMP>']
  --sitemap-from-date TEXT  YYYY-MM-DD string to filter websites modified
                            after this date in sitemaps
  --wacz-output-file TEXT   Filepath to write WACZ archive file to. Can be a
                            local filepath or an S3 URI, e.g.
                            s3://bucketname/filename.xml.
  --num-workers INTEGER     Number of parallel thread workers for crawler.
                            [Default 2]
  --btrix-args-json TEXT    JSON formatted string of additional args to pass
                            to browsertrix-crawler,
                            https://github.com/webrecorder/browsertrix-
                            crawler#crawling-configuration-options
  -h, --help                Show this message and exit.
```
    
## Browsertrix Crawl Configuration

A layered approach is used for configuring the browsertrix crawl part:
1. defaults defined in `Crawler` class that initialize the base crawler command
2. configuration YAML file read and applied by the crawler
3. runtime CLI arguments for this app that override a subset of defaults or YAML defined configurations

Ultimately, these combine to provide the crawler configurations defined here: https://github.com/webrecorder/browsertrix-crawler#crawling-configuration-options.

### Why this approach?

Some arguments are required (e.g. generating CDX index, generating a WACZ archive, etc.) for this harvester to work with the crawl results and therefore set as defaults, some are complex to define as command line arguments (e.g. seeds and exclusion patterns), and some are commonly overriden at runtime (e.g. last modified date for URLs to include).

It is expected that:
  * defaults will rarely need to be overriden
  * configuration YAML is mostly dedicated to defining seeds, exclusion patterns, and other infrequently changing configurations
  * runtime args for this app, `--sitemap-from-date`, change frequently and are therefore better exposed in this way vs defaults or YAML values    

### How to provide the configuration YAML

For local testing, it's advised to put the configuration YAML in the `output/`, e.g. `output/my-test-config.yaml`.  The host machine `output` directory is mounted to `/crawls` in the container, allowing you to kick off the crawl with something like:

```shell
--config-yaml-file="/crawls/my-test-config.yaml"
```

Or, see the local harvest test in the Makefile that is utilizing a test fixture:
```shell
--config-yaml-file="/browsertrix-harvester/tests/fixtures/lib-website-homepage.yaml"
```
                                                
For deployed instances of this harvester -- e.g. invoked by the TIMDEX pipeline -- it's preferred to store the config YAML in S3 and pass that URI, e.g.:
```shell
--config-yaml-file="s3://timdex-extract-dev-222053980223/browsertrix-harvester-crawl-configs/library-wordpress.yaml"
```

## Convenience Make Commands

### Local Test Crawl

```shell
make test-harvest-local
```
  * Performs a crawl using the container mounted config YAML `/browsertrix-harvest/tests/fixtures/lib-website-homepage.yaml`
  * Metadata is written to container directory `/crawls/collections/homepage/homepage.xml`, which is mounted and available in the local `output/` folder 

## Troubleshooting

### Cannot read/write from S3 for a LOCAL docker container harvest

If you are seeing errors like,

```text
botocore.exceptions.NoCredentialsError: Unable to locate credentials
```

it's likely that:
1. either the config YAML or output files are attempting to read/write from S3 
2. the container does not have AWS credentials to work with

The Pipfile command `harvest-dockerized` mounts your host machine's `~/.aws` folder into the container to provide AWS credentials.  Copy/pasting credentials into the calling terminal is not sufficient.  Either `aws configure sso` or manually setting `~/.aws/credentials` file is required.