# browsertrix-harvester architecture

This CLI application extends [Browsertrix-Crawler](https://github.com/webrecorder/browsertrix-crawler) as the base docker image, providing an Ubuntu container that has both the somewhat complex browsertrix-crawler installed and configured, and a Pipenv virtual environment for the CLI app that is exposed for use.

```dockerfile
# extend the browsertrix-crawler docker image
FROM webrecorder/browsertrix-crawler:latest
# ...
# ...
```

NOTE: this is different from other python CLI apps, which generally use `python:3.11-slim` as the base image.

## Web Crawls

Any actions that trigger a browsertrix web crawl will not work outside of a container context.  A decorator `harvester.utils.require_container` has been created that can be used to decorate functions or methods that should not run outside of a container context.  This decorator looks for EITHER of the following conditions to be true:
  * the file `/.dockerenv` exists; indicates locally running container
  * the env var `AWS_EXECUTION_ENV` is set; indicates Fargate ECS task

At this time, only the method `Crawler.crawl` has this treatment.

## Code Architecture

```mermaid
---
title: Class Diagrams
---
classDiagram
    class Cli{
        harvest()        
    }
    class Crawler{
        crawl_name: str
        config_yaml_filepath: str
        sitemap_from_date: str
        btrix_args_json: str[JSON]
        wacz_filepath: str
        crawl_output_dir: str
        crawl() -> WACZ archive
    }
    class CrawlParser{
        wacz_filepath: str
        archive: ZipFile
        websites_df: DataFrame
        generate_metadata() -> DataFrame        
    }
    class CrawlMetadataRecords{
        df: DataFrame
        write() -> File
    }
    Crawler <|-- Cli
    CrawlParser <|-- Cli
    CrawlMetadataRecords <|-- CrawlParser
    
```

## Flow Diagrams

### Local Development
```mermaid
---
title: Local Development
---
flowchart LR
    
    %% host machine
    pipenv_cmd("Pipenv Cmd")
    output_folder("/output/crawls")
    
    %% docker container
    cli_harvest("CLI.harvest()")
    crawler("class Crawler")
    parser("class CrawlParser")
    metadata("class CrawlMetadataRecords")
    crawls_folder("/crawls")
    btrix("Browsertrix Node App")
    
    %% anywhere
    output_wacz("WACZ archive file")
    output_metadata("Metadata Records XML")
    
    pipenv_cmd --> cli_harvest
    output_folder -. mount .- crawls_folder
    
    subgraph Host Machine
        pipenv_cmd
        output_folder
        output_wacz
        output_metadata
        
        output_wacz -. inside .- output_folder
        output_metadata -. inside .- output_folder
    end
    
    subgraph Docker Container 
        btrix
        crawls_folder
        cli_harvest -->|Step 1: call| crawler
        crawler -->|Step 2: call\nvia subprocess| btrix        
        btrix -->|writes to| crawls_folder
        cli_harvest -->|Step 4: call| parser
        parser -->|reads from| crawls_folder
        parser --> metadata
    end
    
    cli_harvest -->|"Step 3: write (optional)"| output_wacz
    metadata -->|Step 5: write| output_metadata
    
```

### Deployed

```mermaid
---
title: Deployed
---
flowchart LR
    
    %% aws events
    aws_event("AWS Event")
    pipenv_cmd("Pipenv Cmd")
    
    %% docker container
    cli_harvest("CLI.harvest()")
    crawler("class Crawler")
    parser("class CrawlParser")
    metadata("class CrawlMetadataRecords")
    crawls_folder("/crawls")
    btrix("Browsertrix Node App")
    
    %% anywhere
    output_wacz("WACZ archive file")
    output_metadata("Metadata Records XML")
    
    aws_event --> pipenv_cmd
    
    subgraph Docker Container
        pipenv_cmd --> cli_harvest
        cli_harvest -->|Step 1: call| crawler
        crawler -->|Step 2: call\nvia subprocess| btrix        
        btrix -->|writes to| crawls_folder
        cli_harvest -->|Step 4: call| parser
        parser -->|reads from| crawls_folder
        parser --> metadata
    end
    
    cli_harvest -->|"Step 3: write (optional)"| output_wacz
    metadata -->|Step 5: write| output_metadata
    
    subgraph S3 bucket
        output_wacz
        output_metadata
    end
    
```