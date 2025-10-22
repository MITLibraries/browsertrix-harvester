# Crawl Data Parsing

What sets this application apart from just a web crawl is it provides the option to create structured metadata records from the crawl. This is the work of the `harvester.parse.CrawlMetadataParser` class. 

This is invoked by including the flag `--metadata-output-file` when performing a `harvest` command.  The file extension -- `jsonl`, `.tsv`, or `.csv` -- dictates the output file type.  

Metadata is extracted in the following way:
1. The crawl is performed, and a WACZ file is saved inside the container
2. Data from multiple parts of the crawl is extracted and combined into a single dataframe
3. HTML content for each website is parsed from the WARC files, accessed through the WACZ file
4. Additional metadata is extracted from that HTML content
5. The original dataframe of websites is extended with this additional metadata generated from the HTML 
6. Lastly, this is written locally, or to S3, as a JSONLines, XML, TSV, or CSV file

An example record from a JSONLines output file looks like this:

```jsonl
{"url": "https://www-test.libraries.mit.edu/borrow/", "cdx_warc_filename": "rec-110ed00ee03c-homepage-20251020180949760-0.warc.gz", "cdx_title": "Borrow & request | MIT Libraries", "cdx_offset": "2482", "cdx_length": "17796", "og_title": "Borrow & request | MIT Libraries", "og_type": "website", "og_image": "https://www-test.libraries.mit.edu/app/themes/mitlib-parent/images/mit-libraries-logo-black-yellow-1200-1200.png", "og_url": "https://www-test.libraries.mit.edu/borrow/", "og_image_type": "image/png", "og_image_width": "1200", "og_image_height": "1200", "og_image_alt": "MIT Libraries logo", "og_description": "On this page: Visit us Borrow & request MIT Materials Borrow & request materials from other libraries Get materials for course reserves Return physical materials On campus Other shipping options Policies Loan periods Recalls Renewals allowed Fines Visit us in person See hours and locations. Visitors may access open library locations during MIT’s public entrance hours. Borrow & request MIT materials Your MIT ID is your library card; either physical or Mobile ID are acceptable. MIT faculty, students, staff, and retirees* automatically receive borrowing privileges. See special user types for information about borrowing privileges for other groups. *Retirees may need to verify eligibility with the […]", "fulltext": null, "fulltext_keywords": "Web of Science,Borrow,Search,request,Borrow Direct,Materials,Borrow Direct Request,Account Search Account,Hours,reserves Borrow Direct,Interlibrary Borrowing,Research,Research support,Borrowing,Collections,reserves,faculty,Search Account Contact,Account,locations"}
```

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

The WACZ files `pages/pages.jsonl` and `pages/extraPages.jsonl` are what create the canonical list of websites to be considered for metadata records.  While a web crawl may make hundreds of HTTP requests to gather Javascript, CSS, JSON, or any other supporting files, what we are most interested in are HTML pages (websites) that were directly included as seeds or discovered via the crawl configurations.

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

The `CrawlMetadataParser` uses all these when building a dataframe of metadata records, roughly following this flow:

1. get list of URLs from `pages.jsonl` and `extraPages.jsonl`
2. get other metadata and associated WARC files for those URLs from the CDX index
3. read the binary content (HTML) from the WARC files; uses offsets and lengths
4. perform some content extraction and analysis of the HTML

The end result is a dataframe of metadata about pages crawled.  As of this writing, this dataframe can be serialized as XML, TSV, or CSV; this is the work of the `harvester.parse.CrawlMetadataRecords` class. 

## Is this parsing of metadata records opinionated?

Yes, very!

This application was designed to support the crawling of the MIT Libraries WordPress sites.  As such, the `CrawlMetadataParser` has class properties that define what HTML tags contain metadata about the page and include this in the final output.  While some of the generated metadata fields are agnostic to the source or even the HTML itself -- e.g. URL, mimetype, etc. -- other metadata properties like `og_description` are derived from very specific HTML tags that may not be present on non-library websites.  

In the event this application needs to be extended to crawl other websites, and generate metadata records about those pages, this class will need to be reworked to provide a mapping of HTML elements to metadata properties.
 

