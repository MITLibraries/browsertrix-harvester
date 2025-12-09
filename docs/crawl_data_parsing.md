# Crawl Data Parsing

This application extends the work of a web crawler to structure and return data about HTML (websites) crawled.  The resulting records include some light metadata about the page and the full, rendered HTML as captured during the crawl.  This is the work of the `harvester.parse.CrawlRecordsParser` class. 

This is invoked by including the flag `--records-output-file` when performing a `harvest` command.  The file extension -- `jsonl`, `.tsv`, or `.csv` -- dictates the output file type.

Records are extracted in the following way:
1. The crawl is performed, and a WACZ file is saved inside the container
2. Data from multiple parts of the crawl is extracted and combined into a single dataframe
3. HTML content for each website is parsed from the WARC files, accessed through the WACZ file
5. The original dataframe of websites is extended with this additional data generated from, and including, the HTML 
6. Lastly, this is written locally, or to S3, as a JSONLines, XML, TSV, or CSV file

## What crawled sites are included as records?

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

Note the [WACZ](https://replayweb.page/docs/wacz-format) file here, `homepage.wacz` (where "homepage" is an arbitrary `--crawl-name`).  This file is a compressed form of the entire crawl, and is the only asset parsed by this application when generating records.  This is handy for multiple reasons:
  * this file can be saved or copied, representing the crawl in its totality
  * parsing data from the crawl is only concerned with a single file as the entrypoint (though multiple files are later accessed inside) allowing creation of records even from a remote file in S3

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

The WACZ files `pages/pages.jsonl` and `pages/extraPages.jsonl` are what create the canonical list of websites to be considered for records.  While a web crawl may make hundreds of HTTP requests to gather Javascript, CSS, JSON, or any other supporting files, what we are most interested in are HTML pages (websites) that were directly included as seeds or discovered via the crawl configurations.

While these JSONL files provide a canonical list of URLs that records will be generated for, they don't provide all the required data for those records.  See more about that [below](#how-are-records-created).

## How are records created?

Records are created from multiple parts of the crawl:

  * `pages.jsonl` and `extraPages.jsonl` files:
    * page URL
    * raw, extracted text from the website HTML (no tags, just text)
  * `index.cdx.gz`, a [CDX](https://iipc.github.io/warc-specifications/specifications/cdx-format/cdx-2015/) index:
    * which WARC file contains the page's binary content as rendered by the crawling
    * mimetype of the asset (e.g. `text/html`)
    * some other information about the HTTP request (e.g. redirects, status codes, etc.)
  * WARC files
    * actual binary content for each HTTP request, i.e. the fully rendered HTML for a website

The `CrawlRecordsParser` uses all these when building a dataframe of records, roughly following this flow:

1. get list of URLs from `pages.jsonl` and `extraPages.jsonl`
2. get CDX data and associated WARC files for those URLs from the CDX index
3. read the binary content (HTML) from the WARC files; uses offsets and lengths
4. include the full HTML for that page in the output record

The end result is structured data of pages crawled.  As of this writing, this dataframe can be serialized as XML, TSV, CSV, or JSONLines; this is the work of the `harvester.parse.CrawlRecords` class.
 

