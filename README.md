# browsertrix-harvester

CLI app for performing a web crawl via [Browsertrix-Crawler](https://github.com/webrecorder/browsertrix-crawler) and optionally parsing structured metadata records from the crawl output [WACZ](https://replayweb.page/docs/wacz-format) file.

One of the primary value adds of this application, as opposed to just running the browsertrix-crawler, is the ability to extract structured metadata records for websites crawled. For more information, see [Crawl Data Parsing](docs/crawl_data_parsing.md).


## Architecture

See [architecture docs](docs/architecture.md).

## Development

When performing web crawls, this application invokes browsertrix-crawler.  While possible to install browsertrix-crawler on your local machine, this application is oriented around running as a Docker container where it is already installed.  For this reason, the pipenv convenience command `harvester-dockerized` has been created.

- To install with dev dependencies: `make install`
- To update dependencies: `make update`
- To run unit tests: `make test`
- To lint the repo: `make lint`
- Build local docker image: `make docker-build`
- To run the app:
  - Non-Dockerized: `pipenv run harvester --help`
    - Works locally for many things but will throw error for actions that perform crawls
  - Dockerized: `make docker-shell`
    - Shell into local container and run `pipenv run harvester --help`

### Local Test Crawl
```shell
make run-harvest-local
```

This Make command kicks off a harvest via a local Docker container.  The Make command reflects some ways in which a harvest can be configured, including local or S3 filepath to a configuration YAML, setting an output metadata file, and even passing in miscellaneous browsertrix arguments to the crawler not explicitly defined as CLI parameters in this app.

The argument `--metadata-output-file="/crawls/collections/homepage/homepagejsonl"` instructs the harvest to parse metadata records from the crawl, which are written to the container, and should then be available on the _host_ machine at: `output/crawls/collections/homepage/homepagejsonl`.

### Remote Test Crawl

```shell
make run-harvest-dev
```
  * Set AWS credentials are required in calling context
  * Kicks off an ECS Fargate task in Dev1
  * WACZ file and metadata file are written to S3 at `timdex-extract-dev-222053980223/librarywebsite/test-harvest-ecs-<TIMESTAMP>.xml|jsonl|wacz`

## CLI commands

### `harvester`

```text
Usage: -c [OPTIONS] COMMAND [ARGS]...

Options:
  -v, --verbose  Pass to log at debug level instead of info
  -h, --help     Show this message and exit.

Commands:
  docker-shell               Run a bash shell inside the docker container.
  generate-metadata-records  Generate metadata records from a WACZ file.
  harvest                    Perform crawl and generate metadata records.
  parse-url-content          Get HTML for a single URL.
```

### `harvester docker-shell`
```text
Usage: -c docker-shell [OPTIONS]

  Run a bash shell inside the docker container.

  The decorator utils.require_container is used to ensure a docker container
  context for running a bash shell.

Options:
  -h, --help  Show this message and exit.
```

### `harvester parse-url-content`
```text
Usage: -c parse-url-content [OPTIONS]

  Get HTML for a single URL.

  This CLI command extracts the fully rendered content of a specific URL from
  a web crawl WACZ file. By printing/echoing the contents, this can be
  redirected via stdout in the calling context.

Options:
  --wacz-input-file TEXT  Filepath to WACZ archive from crawl  [required]
  --url TEXT              Website URL to parse HTML content for  [required]
  -h, --help              Show this message and exit.
```

### `harvester generate-metadata-records`

```text
Usage: -c generate-metadata-records [OPTIONS]

  Generate metadata records from a WACZ file.

  This is a convenience CLI command.  Most commonly, the command 'harvest'
  will be used that performs a web crawl and generates metadata records from
  that crawl as under the umbrella of a single command.  This CLI command
  would be useful if a crawl is already completed (a WACZ file exists) and
  only the generation of metadata records is needed.

Options:
  --wacz-input-file TEXT       Filepath to WACZ archive from crawl  [required]
  --metadata-output-file TEXT  Filepath to write metadata records to. Can be a
                               local filepath or an S3 URI, e.g.
                               s3://bucketname/filename.jsonl.  Supported file
                               type extensions: [jsonl, xml,tsv,csv].
  --include-fulltext           Set to include parsed fulltext from website in
                               generated structured metadata.
  -h, --help                   Show this message and exit.
```

### `harvester harvest`

```text
Usage: -c harvest [OPTIONS]

  Perform crawl and generate metadata records.

  Perform a web crawl and generate metadata records from the resulting WACZ
  file.

Options:
  --config-yaml-file TEXT         Filepath of browsertrix config YAML. Can be
                                  a local filepath or an S3 URI, e.g.
                                  s3://bucketname/crawl-config.yaml
                                  [required]
  --crawl-name TEXT               Optional override for crawl name. [Default
                                  'crawl-<TIMESTAMP>']
  --sitemap TEXT                  Sitemap URL to parse and then provide the
                                  crawler with an explicit list of URLs as
                                  seeds, e.g.
                                  'https://libraries.mit.edu/sitemap.xml'.
                                  Repeatable.
  --sitemap-from-date TEXT        YYYY-MM-DD string to filter websites
                                  modified on/after this date in sitemaps
  --sitemap-to-date TEXT          YYYY-MM-DD string to filter websites
                                  modified before this date in sitemaps
  --wacz-output-file TEXT         Filepath to write WACZ archive file to. Can
                                  be a local filepath or an S3 URI, e.g.
                                  s3://bucketname/filename.jsonl.
  --metadata-output-file TEXT     Filepath to write metadata records to. Can
                                  be a local filepath or an S3 URI, e.g.
                                  s3://bucketname/filename.jsonl.  Supported
                                  file type extensions: [jsonl,xml,tsv,csv].
  --sitemap-urls-output-file TEXT
                                  If --parse-sitemaps-pre-crawl is set,
                                  optionally write a text file of
                                  discoveredURLs parsed from sitemap(s).
  --previous-sitemap-urls-file TEXT
                                  If passed, a previous file with all URLs
                                  from sitemap parsing will be read and used
                                  to determine if URLs have since been removed
                                  and should be marked as 'deleted' as an
                                  output metadata record.
  --include-fulltext              Set to include parsed fulltext from website
                                  in generated structured metadata.
  --extract-fulltext-keywords     Set to use YAKE to extract keywords from
                                  fulltext.
  --num-workers INTEGER           Number of parallel thread workers for
                                  crawler. Crawler defaults to 1 if not set
                                  here, in the configuration YAML, or ad hoc
                                  via --btrix-args-json.
  --btrix-args-json TEXT          JSON formatted string of additional args to
                                  pass to browsertrix-crawler,
                                  https://github.com/webrecorder/browsertrix-
                                  crawler#crawling-configuration-options
  -h, --help                      Show this message and exit.

```

This is the primary command for this application.  This performs a web crawl, then optionally parses the results of that crawl into structured data and writes to a specific location.

See section [Browsertrix Crawl Configuration](docs/crawl_configuration.md) for details about configuring the browsertrix crawl part of a harvest.

**NOTE:** if _neither_ `--wacz-output-file` or `--metadata-output-file` is set, an error will be logged and the application will exit before a crawl is performed as there would be no output.

## Environment Variables

### Optional

```dotenv
WORKSPACE=None
SENTRY_DSN=None # If set to a valid Sentry DSN, enables Sentry exception monitoring. This is not needed for local development.
```

## Troubleshooting

### Cannot read/write from S3 for a LOCAL docker container harvest

If you are seeing errors like,

```text
botocore.exceptions.NoCredentialsError: Unable to locate credentials
```

it's likely that:
1. either the config YAML or output files are attempting to read/write from S3 
2. the container does not have AWS credentials to work with

The Pipfile command `harvester-dockerized` mounts your host machine's `~/.aws` folder into the container to provide AWS credentials.  Copy/pasting credentials into the calling terminal is not sufficient.  Either `aws configure sso` or manually setting `~/.aws/credentials` file is required.

## Related Assets
This is a repository that provides the Browsertrix Harvester. The following application infrastructure repositories are related to this repository:

[TIMDEX Infrastructure](https://github.com/MITLibraries/mitlib-tf-workloads-timdex-infrastructure)
[ECR](https://github.com/MITLibraries/mitlib-tf-workloads-ecr)

## Maintainers
* Owner: See [CODEOWNERS](./.github/CODEOWNERS)
* Team: See [CODEOWNERS](./.github/CODEOWNERS)
* Last Maintenance: 2025-10