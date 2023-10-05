# Crawl Data Parsing

As mentioned in the [project README](../README.md), one thing that sets this application apart from just a web crawl is the parsing of metadata records that represent the websites crawled.  This is the work of the `harvester.parse.CrawlParser` class.

## What crawled sites are included as metadata records?

A browsertrix web crawl generates a bunch of files as the result of the crawl:

```text
├── archive
│   ├── rec-20230929152646786455-3e0077b1f009.warc.gz
│   ├── rec-20230929152647253458-3e0077b1f009.warc.gz
│   ├── rec-20230929152648227041-3e0077b1f009.warc.gz
│   ├── rec-20230929152648249931-3e0077b1f009.warc.gz
│   ├── rec-20230929152648436859-3e0077b1f009.warc.gz
│   ├── rec-20230929152648567703-3e0077b1f009.warc.gz
│   ├── rec-20230929152648603443-3e0077b1f009.warc.gz
│   ├── rec-20230929152648639794-3e0077b1f009.warc.gz
│   ├── rec-20230929152649186320-3e0077b1f009.warc.gz
│   └── rec-20230929152649791199-3e0077b1f009.warc.gz
├── homepage.wacz
├── indexes
│   └── index.cdxj
├── logs
│   └── crawl-20230929152634980.log
├── pages
│   └── pages.jsonl
├── static
└── templates
```

Note the [WACZ](https://replayweb.page/docs/wacz-format) file here, `homepage.wacz` (where "homepage" is an arbitrary `--crawl-name`).  This file is a compressed form of the entire crawl, and is the only asset parsed by this application when generating metadata records.  This is handy for multiple reasons:
  * this file can be saved or copied, representing the crawl in its totality
  * parsing data from the crawl is only concerned with a single file as the entrypoint (though multiple files are later accessed inside) allowing creation of metadata records even from a remote file in S3

The structure of the WACZ file is nearly identical to the uncompressed crawl results, with some minor, but important, additions:
```text
.
├── archive
│   ├── rec-20230929152646786455-3e0077b1f009.warc.gz
│   ├── rec-20230929152647253458-3e0077b1f009.warc.gz
│   ├── rec-20230929152648227041-3e0077b1f009.warc.gz
│   ├── rec-20230929152648249931-3e0077b1f009.warc.gz
│   ├── rec-20230929152648436859-3e0077b1f009.warc.gz
│   ├── rec-20230929152648567703-3e0077b1f009.warc.gz
│   ├── rec-20230929152648603443-3e0077b1f009.warc.gz
│   ├── rec-20230929152648639794-3e0077b1f009.warc.gz
│   ├── rec-20230929152649186320-3e0077b1f009.warc.gz
│   └── rec-20230929152649791199-3e0077b1f009.warc.gz
├── datapackage-digest.json
├── datapackage.json
├── indexes
│   ├── index.cdx.gz
│   └── index.idx
├── logs
│   └── crawl-20230929152634980.log
└── pages
    ├── extraPages.jsonl
    └── pages.jsonl
```

The WACZ files `pages/pages.jsonl` and `pages/extraPages.jsonl` are what create the canonical list of websites to be considered for metadata records.  While a web crawl may make hundreds of HTTP requests to gather Javascript, CSS, JSON, or any other supporting files, what we are most interested in are pages (websites) that were directly included as seeds or discovered via the crawl configurations.

While these JSONL files provide a canonical list of URLs that metadata records will be generated for, they don't provide all the required data for those records.  See more about that [below](#how-are-metadata-records-created).

## How are metadata records created?

Metadata records are created from multiple parts of the crawl:

  * `pages.jsonl` and `extraPages.jsonl` files:
    * page URL
    * raw, extracted text from the website HTML (no tags, just text)
  * `index.cdx.gz`, a [CDX](https://iipc.github.io/warc-specifications/specifications/cdx-format/cdx-2015/) index:
    * which WARC file contains the page's binary content as rendered by the crawling
    * mimetype of the asset (e.g. `text/html`)
    * some other information about the HTTP request (e.g. redirects, status codes, etc.)
  * WARC files
    * actual binary content for each HTTP request, i.e. the fully rendered HTML for a website

The `CrawlParser` uses all these when building a dataframe of metadata records, roughly following this flow:

1. get list of URLs from `pages.jsonl` and `extraPages.jsonl`
2. get other metadata and associated WARC files for those URLs from the CDX index
3. read the binary content (HTML) from the WARC files; uses offsets and lengths
4. perform some content extraction and analysis of the HTML

The end result is a dataframe of metadata about pages crawled.  As of this writing, this dataframe can be serialized as XML, TSV, or CSV; this is the work of the `harvester.parse.CrawlMetadataRecords` class. 

## Is this parsing of metadata records opinionated?

Yes, very!

This application was designed to support the crawling of the MIT Libraries WordPress sites.  As such, the `CrawlParser` has class properties that define what HTML tags contain metadata about the page and include this in the final output.  While some of the generated metadata fields are agnostic to the source or even the HTML itself -- e.g. URL, mimetype, etc. -- other metadata properties like `og_description` are derived from very specific HTML tags that may not be present on non-library websites.  

In the event this application needs to be extended to crawl other websites, and generate metadata records about those pages, this class will need to be reworked to provide a mapping of HTML elements to metadata properties.
 

