### This is the Terraform-generated header for browsertrix-harvester-dev. If  ###
###   this is a Lambda repo, uncomment the FUNCTION line below  ###
###   and review the other commented lines in the document.     ###
ECR_NAME_DEV:=browsertrix-harvester-dev
ECR_URL_DEV:=222053980223.dkr.ecr.us-east-1.amazonaws.com/browsertrix-harvester-dev
### End of Terraform-generated header                            ###
SHELL=/bin/bash
DATETIME:=$(shell date -u +%Y%m%dT%H%M%SZ)

help: ## Print this message
	@awk 'BEGIN { FS = ":.*##"; print "Usage:  make <target>\n\nTargets:" } \
/^[-_[:alpha:]]+:.?*##/ { printf "  %-15s%s\n", $$1, $$2 }' $(MAKEFILE_LIST)

### Dependency commands ###
install: # install python dependencies
	pipenv install --dev
	pipenv run pre-commit install

update: install ## Update all Python dependencies
	pipenv clean
	pipenv update --dev

### Test commands ###
test: ## Run tests and print a coverage report
	pipenv run coverage run --source=harvester -m pytest -vv
	pipenv run coverage report -m

coveralls: test
	pipenv run coverage lcov -o ./coverage/lcov.info

# linting commands
lint: black mypy ruff safety 

black:
	pipenv run black --check --diff .

mypy:
	pipenv run mypy .

ruff:
	pipenv run ruff check .

safety:
	pipenv check
	pipenv verify

# apply changes to resolve any linting errors
lint-apply: black-apply ruff-apply

black-apply: 
	pipenv run black .

ruff-apply: 
	pipenv run ruff check --fix .

docker-shell:
	pipenv run harvester-dockerized docker-shell

dist-local:
	docker build -t $(ECR_NAME_DEV):latest .

# Test local harvest
run-harvest-local:
	pipenv run harvester-dockerized --verbose harvest \
	--crawl-name="homepage" \
	--config-yaml-file="/browsertrix-harvester/tests/fixtures/lib-website-homepage.yaml" \
	--metadata-output-file="/crawls/collections/homepage/homepage.xml" \
	--num-workers 4 \
	--btrix-args-json='{"--maxPageLimit":"15"}'

# Test Dev1 harvest
run-harvest-dev:
	CRAWL_NAME=test-harvest-ecs-$(DATETIME); \
	aws ecs run-task \
		--cluster timdex-dev \
		--task-definition timdex-browsertrixharvester-dev \
		--launch-type="FARGATE" \
		--region us-east-1 \
		--network-configuration '{"awsvpcConfiguration": {"subnets": ["subnet-0488e4996ddc8365b","subnet-022e9ea19f5f93e65"], "securityGroups": ["sg-044033bf5f102c544"]}}' \
		--overrides '{"containerOverrides": [ {"name":"browsertrix-harvester", "command": ["--verbose", "harvest", "--crawl-name", "'$$CRAWL_NAME'", "--config-yaml-file", "/browsertrix-harvester/tests/fixtures/lib-website-homepage.yaml", "--metadata-output-file", "s3://timdex-extract-dev-222053980223/librarywebsite/'$$CRAWL_NAME'.xml", "--wacz-output-file", "s3://timdex-extract-dev-222053980223/librarywebsite/'$$CRAWL_NAME'.wacz", "--num-workers", "2"]}]}'

# Test local URL content parsing
test-parse-url-content:
	pipenv run harvester parse-url-content \
	--wacz-input-file="tests/fixtures/example.wacz" \
	--url="https://example.com/hello-world"

### Terraform-generated Developer Deploy Commands for Dev environment ###
dist-dev: ## Build docker container (intended for developer-based manual build)
	docker build --platform linux/amd64 \
	    -t $(ECR_URL_DEV):latest \
		-t $(ECR_URL_DEV):`git describe --always` \
		-t $(ECR_NAME_DEV):latest .

publish-dev: dist-dev ## Build, tag and push (intended for developer-based manual publish)
	docker login -u AWS -p $$(aws ecr get-login-password --region us-east-1) $(ECR_URL_DEV)
	docker push $(ECR_URL_DEV):latest
	docker push $(ECR_URL_DEV):`git describe --always`

### Terraform-generated manual shortcuts for deploying to Stage. This requires  ###
###   that ECR_NAME_STAGE, ECR_URL_STAGE, and FUNCTION_STAGE environment        ###
###   variables are set locally by the developer and that the developer has     ###
###   authenticated to the correct AWS Account. The values for the environment  ###
###   variables can be found in the stage_build.yml caller workflow.            ###
dist-stage: ## Only use in an emergency
	docker build --platform linux/amd64 \
	    -t $(ECR_URL_STAGE):latest \
		-t $(ECR_URL_STAGE):`git describe --always` \
		-t $(ECR_NAME_STAGE):latest .

publish-stage: ## Only use in an emergency
	docker login -u AWS -p $$(aws ecr get-login-password --region us-east-1) $(ECR_URL_STAGE)
	docker push $(ECR_URL_STAGE):latest
	docker push $(ECR_URL_STAGE):`git describe --always`