# browsertrix-harvester

CLI app for performing a web crawl via [Browsertrix-Crawler](https://github.com/webrecorder/browsertrix-crawler), and optionally parsing structured metadata records from the crawl output [WACZ](https://replayweb.page/docs/wacz-format) file.

## Architecture

See [architecture docs](docs/architecture.md).

## Development

**NOTE**: When performing web crawls, this application invokes browsertrix-crawler.  While possible to install browsertrix-crawler on your local machine, this application is oriented around running as a Docker container where it is already installed.  For this reason, the pipenv convenience command `harvester-dockerized` has been created.

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
- Build docker image: `make dist-local`
  - builds local image `browsertrix-harvester-dev:latest`
- To run the app:
  - Non-Dockerized: `pipenv run harvester --help`
    - works locally for many things, but will throw error for actions that perform crawls
  - Dockerized: `pipenv run harvester-dockerized --help`
    - provides full functionality by running as a docker container
    - host machine `~/.aws` directory mounted into container to provide AWS credentials to container
    - points back to the pipenv command `harvester` 

### Testing and Linting

```shell
make test
make lint
```

#### Local Test Crawl
```shell
make run-harvest-local
```

This Make command kicks off a harvest via a local docker container.  The Make command reflects some ways in which a harvest can be configured, including local or S3 filepath to a configuration YAML, setting an output metadata file, and even passing in miscellaneous browsertrix arguments to the crawler not explicitly defined as CLI parameters in this app.

The argument `--metadata-output-file="/crawls/collections/homepage/homepage.xml"` instructs the harvest to parse metadata records from the crawl, which are written to the container, and should then be available on the _host_ machine at: `output/crawls/collections/homepage/homepage.xml`.

### Remote Test Crawl

```shell
make run-harvest-dev
```
  * Set AWS credentials are required in calling context
  * Kicks off an ECS Fargate task in Dev1
  * WACZ file and metadata file are written to S3 at `timdex-extract-dev-222053980223/librarywebsite/test-harvest-ecs-$CURRENT_DATE.xml|wacz`

## CLI commands

### Main
```shell
pipenv run harvester
```
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

### Shell environment
```shell
pipenv run harvester shell
```
```text
Usage: -c shell [OPTIONS]

  Run a bash shell inside the docker container.

Options:
  -h, --help  Show this message and exit.
```

### Parse URL content from crawl
```shell
pipenv run harvester parse-url-content
```
```text
Usage: -c parse-url-content [OPTIONS]

  Get HTML content for a single URL from a WACZ file.

  This CLI command extracts the fully rendered content of a specific URL from
  a web crawl WACZ file. By printing/echoing the contents, this can be
  redirected via stdout in the calling context.

Options:
  --wacz-input-file TEXT  Filepath to WACZ archive from crawl  [required]
  --url TEXT              Website URL to parse HTML content for  [required]
  -h, --help              Show this message and exit.
```

### Generate metadata records from a WACZ file
```shell
pipenv run harvester generate-metadata-records
```
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
                               s3://bucketname/filename.xml.  Supported file
                               type extensions: [xml,tsv,csv].
  --include-fulltext           Set to include parsed fulltext from website in
                               generated structured metadata.
  -h, --help                   Show this message and exit.
```


### Perform web crawl and harvest data
This is the primary command for this application.  This performs a web crawl, then optionally parses the results of that crawl into structured data and writes to a specific location.

See section [Browsertrix Crawl Configuration](#browsertrix-crawl-configuration) for details about configuring the browsertrix crawl part of a harvest.

**NOTE:** if _neither_ `--wacz-output-file` or `--metadata-output-file` is set, an error will be logged and the application will exit before a crawl is performed as there would be no output.

```shell
# run harvest as local docker container
pipenv run harvester-dockerized harvest

# command used for deployed ECS task
pipenv run harvester harvest
```
```text
Usage: -c harvest [OPTIONS]

  Perform a crawl and generate metadata records from the resulting WACZ file.

Options:
  --config-yaml-file TEXT      Filepath of browsertrix config YAML. Can be a
                               local filepath or an S3 URI, e.g.
                               s3://bucketname/crawl-config.yaml  [required]
  --crawl-name TEXT            Optional override for crawl name. [Default
                               'crawl-<TIMESTAMP>']
  --sitemap-from-date TEXT     YYYY-MM-DD string to filter websites modified
                               after this date in sitemaps
  --wacz-output-file TEXT      Filepath to write WACZ archive file to. Can be
                               a local filepath or an S3 URI, e.g.
                               s3://bucketname/filename.xml.
  --metadata-output-file TEXT  Filepath to write metadata records to. Can be a
                               local filepath or an S3 URI, e.g.
                               s3://bucketname/filename.xml.  Supported file
                               type extensions: [xml,tsv,csv].
  --include-fulltext           Set to include parsed fulltext from website in
                               generated structured metadata.
  --num-workers INTEGER        Number of parallel thread workers for crawler.
                               [Default 2]
  --btrix-args-json TEXT       JSON formatted string of additional args to
                               pass to browsertrix-crawler,
                               https://github.com/webrecorder/browsertrix-
                               crawler#crawling-configuration-options
  -h, --help                   Show this message and exit.
```
    
## Browsertrix Crawl Configuration

A layered approach is used for configuring the browsertrix web crawl part of a harvest:
1. Defaults defined in `Crawler` class that initialize the base crawler command
2. Configuration YAML file read and applied by the crawler
3. Runtime CLI arguments for this app that override a subset of defaults or YAML defined configurations

Ultimately, these combine to provide the crawler configurations defined here: https://github.com/webrecorder/browsertrix-crawler#crawling-configuration-options.

### Why this approach?

Some arguments are required (e.g. generating CDX index, generating a WACZ archive, etc.) for this harvester to work with the crawl results and therefore set as defaults, some are complex to define as command line arguments (e.g. seeds and exclusion patterns), and some are commonly overriden at runtime (e.g. last modified date for URLs to include).

It is expected that:
  * defaults will rarely need to be overriden
  * configuration YAML is mostly dedicated to defining seeds, exclusion patterns, and other infrequently changing configurations
  * runtime args for this app, e.g. `--sitemap-from-date`, change frequently and are therefore better exposed in this way vs defaults or YAML values    

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

## Extract Metadata Records

One of the primary value adds of this application, as opposed to just running the browsertrix-crawler, is the ability to extract structured metadata records for websites crawled.  This is invoked by including the flag `--metadata-output-file` when performing a `harvest` command.  The file extension -- `.xml`, `.tsv`, or `.csv` -- dictates the output file type.

Metadata is extracted in the following way:
1. The crawl is performed, and a WACZ file is saved inside the container
2. Data from multiple parts of the crawl is extracted and combined into a single dataframe
3. HTML content for each website is parsed from the WARC files
4. Additional metadata is extracted from that HTML content
5. The original dataframe of websites is extended with this additional metadata generated from the HTML 
6. Lastly, this is written locally, or to S3, as an XML, TSV, or CSV file

An example record from an XML output file looks like this:
```xml
<records>
    <record>
        <url>https://libraries.mit.edu/research-support/new-shortcut-urls/</url>
        <cdx_warc_filename>rec-20230926164856849501-5c7776aa2137.warc.gz
        </cdx_warc_filename>
        <cdx_title>New shortcut URLs | MIT Libraries</cdx_title>
        <cdx_offset>63709</cdx_offset>
        <cdx_length>38766</cdx_length>
        <og_title>New shortcut URLs | MIT Libraries</og_title>
        <og_type>website</og_type>
        <og_image>
            https://libraries.mit.edu/app/themes/mitlib-parent/images/mit-libraries-logo-black-yellow-1200-1200.png
        </og_image>
        <og_url>https://libraries.mit.edu/research-support/new-shortcut-urls/</og_url>
        <og_image_type>image/png</og_image_type>
        <og_image_width>1200</og_image_width>
        <og_image_height>1200</og_image_height>
        <og_image_alt>MIT Libraries logo</og_image_alt>
        <fulltext>None</fulltext>
        <fulltext_keywords>home Research support,URLs Research support,Research
            support,support New shortcut,shortcut URLs,shortcut URLs Research,link
            work,n’t my link,URLs,shortcut,home Research,support,Research,URLs
            Research,resources,work,URL,Database list,searchable A-Z Database,research
            guides
        </fulltext_keywords>
        <og_description>Why didn’t my link work? We have updated our shortcut URLs to a
            new format. Most of the old URLs have changed from
            https://libraries.mit.edu/get/resourcename to
            https://libguides.mit.edu/resourcename. How to find the new URLs and other
            resources To find these resources, you can locate them on our browsable,
            filterable, and searchable A-Z Database list. To get the […]
        </og_description>
    </record>
    ...
    ...
</records>
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