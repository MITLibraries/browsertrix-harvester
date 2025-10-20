# Browsertrix Crawl Configuration

A layered approach is used for configuring the browsertrix web crawl part of a harvest:
1. Defaults defined in `Crawler` class that initialize the base crawler command
2. Configuration YAML file read and applied by the crawler
3. Runtime CLI arguments for this app that override a subset of defaults or YAML defined configurations

Ultimately, these combine to provide the crawler configurations defined here: https://github.com/webrecorder/browsertrix-crawler#crawling-configuration-options.

## Why this approach?

Some arguments are required (e.g. generating CDX index, generating a WACZ archive, etc.) for this harvester to work with the crawl results and therefore set as defaults, some are complex to define as command line arguments (e.g. seeds and exclusion patterns), and some are commonly overriden at runtime (e.g. last modified date for URLs to include).

It is expected that:
  * defaults will rarely need to be overriden
  * configuration YAML is mostly dedicated to defining seeds, exclusion patterns, and other infrequently changing configurations
  * runtime args for this app, e.g. `--sitemap-from-date`, change frequently and are therefore better exposed in this way vs defaults or YAML values    

## How to provide the configuration YAML

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