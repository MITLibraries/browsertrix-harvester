# browsertrix-harvester

CLI app for performing a web crawl via [Browsertrix-Crawler](https://github.com/webrecorder/browsertrix-crawler), and optionally parsing structured metadata records from the crawl output [WACZ](https://replayweb.page/docs/wacz-format) file.

## Architecture

See [architecture docs](docs/architecture.md).

## Development

**NOTE**: When performing web crawls, this application invokes browsertrix-crawler.  While theoretically possible to install browsertrix-crawler on your local machine as a callable binary, this application is oriented around running only inside of a Docker container where it is already installed.  For this reason, the pipenv convenience command `btrixharvest-dockerized` has been created (more on this below).

### Build Application

- To install with dev dependencies: `make install`
- To update dependencies: `make update`
- To run unit tests: `make test`
- To lint the repo: `make lint`
- Install pre-commit hooks: `pipenv run pre-commit install`
- Build docker image: `make build-docker`
  - builds local image `browsertrix-harvester-dev:latest`
- To run the app:
  - Non-Dockerized: `pipenv run btrixharvest --help`
    - works locally for many things, but will throw error for actions that perform crawls
  - Dockerized: `pipenv run btrixharvest-dockerized --help`
    - provides full functionality by running as a docker container
    - points back to the pipenv command `btrixharvest` 

### Testing and Linting

```shell
make test
make lint
```

## Environment Variables

```dotenv
WORKSPACE=None
SENTRY_DSN=None# If set to a valid Sentry DSN, enables Sentry exception monitoring. This is not needed for local development.
```

## CLI commands

### Main
```shell
pipenv run btrixharvest
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
pipenv run btrixharvest shell
```
```text
Usage: -c shell [OPTIONS]

  Run a bash shell inside the docker container.

Options:
  -h, --help            Show this message and exit.
```

### Parse URL content from crawl
```shell
pipenv run btrixharvest parse-url-content
```
```text
Usage: -c parse-url-content [OPTIONS]

  Get HTML content for a URL from a WACZ archive file.

  By printing the contents, this can be redirected via stdout in the calling
  context.

Options:
  --wacz-filepath TEXT  Filepath to WACZ archive from crawl  [required]
  --url TEXT            Website URL to parse HTML content for  [required]
  -h, --help            Show this message and exit.
```


### Harvesting data from a web crawl
This is the primary command for this application.  This performs a web crawl, then optionally parses the results of that crawl into structured data and writes to a specific location. 

**NOTE:** if neither `--wacz-output-file` or `--metadata-output-file` is set, a crawl will be performed, but nothing will exist outside of the container after it completes.

```shell
pipenv run btrixharvest-dockerized harvest
```
```text
Usage: -c harvest [OPTIONS]

  Perform a web crawl and parse structured data.

Options:
  --crawl-name TEXT            Name of crawl  [required]
  --config-yaml-file TEXT      Filepath of browsertrix config YAML. Can be a
                               local filepath or an S3 URI, e.g.
                               s3://bucketname/crawl-config.yaml  [required]
  --sitemap-from-date TEXT     YYYY-MM-DD string to filter websites modified
                               after this date in sitemaps
  --wacz-output-file TEXT      Filepath to write WACZ archive file to. Can be
                               a local filepath or an S3 URI, e.g.
                               s3://bucketname/filename.xml.
  --metadata-output-file TEXT  Filepath to write metadata records to. Can be a
                               local filepath or an S3 URI, e.g.
                               s3://bucketname/filename.wacz.
  --include-fulltext           Set to include parsed fulltext from website in
                               generated structured metadata. [Default False]
  --num-workers INTEGER        Number of parallel thread workers for crawler.
                               [Default 2]
  --btrix-args-json TEXT       JSON formatted string of additional args to
                               pass to browsertrix-crawler,
                               https://github.com/webrecorder/browsertrix-
                               crawler#crawling-configuration-options
  -h, --help                   Show this message and exit.
```
    
#### Configuration YAML

There are a couple of options for providing a file for the required `--config-yaml-file` argument:
  * 1- add to, or reuse files from, the local directory `browsertrix_harvester/crawl_configs`
    * on image rebuild, this file will be available in the container at `/btrixharvest/browsertrix_harvester/crawl_configs`
  * 2- provide an S3 file URI

At the time of harvest, for either local or remote files, the application copies the provided file to `/btrixharvest/crawl-config.yaml` inside the container.

## Extracted Metadata

One of the primary value adds of this application, as opposed to just running the browsertrix-crawler, is the ability to extract structured metadata for each website crawled.  This is invoked by including the flag `--metadata-output-file` when performing a `harvest` command.  The file extension -- `.xml`, `.tsv`, or `.csv` -- dictates the output file type.

Metadata is extracted in the following way:
1. the crawl is performed, and a WACZ file is saved inside the container
2. data from the crawl is extracted into a dataframes
3. content for each site crawled is pulled from the WARC files, and metadata is extracted from the HTML
4. this is all combined as a final dataframe
5. this is written locally or to S3 as an XML, TSV, or CSV file

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

## Convenience Make Commands

### Build docker image

```shell
make build-docker
```
  * Puilds a local docker image _without_ specifying an architecture type, making it more widely compatible for local testing

### Local Test Crawl

```shell
make test-crawl-local
```
  * Performs a crawl using the config YAML `/btrixharvest/tests/fixtures/lib-website-homepage.yaml`
  * Metadata is written to `/crawls/collections/homepage/homepage.xml` in the container, which is mounted and available in the local `output/` folder 

### Remote Test Crawl

```shell
make test-harvest-ecs
```
  * NOTE: AWS credentials are required
  * Kicks off an ECS Fargate task in Dev1
  * WACZ file and metadata file are written to S3 at `timdex-extract-dev-222053980223/librarywebsite/<FILE>`