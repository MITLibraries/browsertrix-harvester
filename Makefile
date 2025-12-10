### This is the Terraform-generated header for browsertrix-harvester-dev. If ###
###   this is a Lambda repo, uncomment the FUNCTION line below               ###
###   and review the other commented lines in the document.                  ###
ECR_NAME_DEV := browsertrix-harvester-dev
ECR_URL_DEV := 222053980223.dkr.ecr.us-east-1.amazonaws.com/browsertrix-harvester-dev
CPU_ARCH ?= $(shell cat .aws-architecture 2>/dev/null || echo "linux/amd64")
### End of Terraform-generated header                                        ###
SHELL=/bin/bash
DATETIME:=$(shell date -u +%Y%m%dT%H%M%SZ)

help: # Print this message
	@awk 'BEGIN { FS = ":.*#"; print "Usage:  make <target>\n\nTargets:" } \
/^[-_[:alpha:]]+:.?*#/ { printf "  %-15s%s\n", $$1, $$2 }' $(MAKEFILE_LIST)

#######################
# Dependency commands 
#######################

install: # Install Python dependencies
	pipenv install --dev
	pipenv run pre-commit install

update: install ### Update Python dependencies
	pipenv clean
	pipenv update --dev

######################
# Unit test commands 
######################

test: # Run tests and print a coverage report
	pipenv run coverage run --source=harvester -m pytest -vv
	pipenv run coverage report -m

coveralls: test # Write coverage data to an LCOV report
	pipenv run coverage lcov -o ./coverage/lcov.info

####################################
# Code quality and safety commands
####################################

lint: black mypy ruff safety # Run linters

black: # Run 'black' linter and print a preview of suggested changes
	pipenv run black --check --diff .

mypy: # Run 'mypy' linter
	pipenv run mypy .

ruff: # Run 'ruff' linter and print a preview of errors
	pipenv run ruff check .

safety: # Check for security vulnerabilities and verify Pipfile.lock is up-to-date
	pipenv run pip-audit
	pipenv verify

lint-apply: black-apply ruff-apply # Apply changes with 'black' and resolve 'fixable errors' with 'ruff'

black-apply: # Apply changes with 'black'
	pipenv run black .

ruff-apply: # Resolve 'fixable errors' with 'ruff'
	pipenv run ruff check --fix .

##########
# Docker
##########
docker-build: # Build local image for testing
	docker build -t $(ECR_NAME_DEV):latest .

docker-shell: # Shell into local container for testing
	docker run -it -v $(PWD)/output/crawls:/crawls browsertrix-harvester-dev:latest docker-shell

docker-test-run: # Test local docker container
	docker run -it -v $(PWD)/output/crawls:/crawls browsertrix-harvester-dev:latest

####################
# Harvest commands
####################

run-harvest-local: # Run local harvest
	docker run -it -v $(PWD)/output/crawls:/crawls browsertrix-harvester-dev:latest \
	--verbose \
	harvest \
	--crawl-name="homepage" \
	--config-yaml-file="/browsertrix-harvester/tests/fixtures/lib-website-homepage.yaml" \
	--records-output-file="/crawls/collections/homepage/homepage.jsonl" \
	--num-workers 4 \
	--btrix-args-json='{"--maxPageLimit":"15"}'


run-harvest-dev: # Run harvest as ECS task in Dev
	CRAWL_NAME=test-harvest-ecs-$(DATETIME); \
	aws ecs run-task \
		--cluster timdex-dev \
		--task-definition timdex-browsertrixharvester-dev \
		--launch-type="FARGATE" \
		--region us-east-1 \
		--network-configuration '{"awsvpcConfiguration": {"subnets": ["subnet-0488e4996ddc8365b","subnet-022e9ea19f5f93e65"], "securityGroups": ["sg-044033bf5f102c544"]}}' \
		--overrides '{"containerOverrides": [ {"name":"browsertrix-harvester", "command": ["--verbose", "harvest", "--crawl-name", "'$$CRAWL_NAME'", "--config-yaml-file", "/browsertrix-harvester/tests/fixtures/lib-website-homepage.yaml", "--records-output-file", "s3://timdex-extract-dev-222053980223/librarywebsite/'$$CRAWL_NAME'.jsonl", "--wacz-output-file", "s3://timdex-extract-dev-222053980223/librarywebsite/'$$CRAWL_NAME'.wacz", "--num-workers", "2"]}]}'
 
run-harvest-stage: # Run harvest as ECS task in Stage
	CRAWL_NAME=test-harvest-ecs-$(DATETIME); \
	aws ecs run-task \
		--cluster timdex-stage \
		--task-definition timdex-browsertrixharvester-stage \
		--launch-type="FARGATE" \
		--region us-east-1 \
		--network-configuration '{"awsvpcConfiguration": {"subnets": ["subnet-05df31ac28dd1a4b0","subnet-04cfa272d4f41dc8a"], "securityGroups": ["sg-0f64d9a1101d544d1"]}}' \
		--overrides '{"containerOverrides": [ {"name":"browsertrix-harvester", "command": ["--verbose", "harvest", "--crawl-name", "'$$CRAWL_NAME'", "--config-yaml-file", "/browsertrix-harvester/tests/fixtures/lib-website-homepage.yaml", "--records-output-file", "s3://timdex-extract-stage-840055183494/mitlibwebsite/'$$CRAWL_NAME'.jsonl", "--wacz-output-file", "s3://timdex-extract-stage-840055183494/mitlibwebsite/'$$CRAWL_NAME'.wacz", "--num-workers", "2"]}]}'

parse-url-content-local: # Test local URL content parsing
	pipenv run harvester parse-url-content \
	--wacz-input-file="tests/fixtures/example.wacz" \
	--url="https://example.com/hello-world"

#############
# Terraform
#############

### Terraform-generated Developer Deploy Commands for Dev environment ###
check-arch:
	@ARCH_FILE=".aws-architecture"; \
	if [[ "$(CPU_ARCH)" != "linux/amd64" && "$(CPU_ARCH)" != "linux/arm64" ]]; then \
        echo "Invalid CPU_ARCH: $(CPU_ARCH)"; exit 1; \
    fi; \
	if [[ -f $$ARCH_FILE ]]; then \
		echo "latest-$(shell echo $(CPU_ARCH) | cut -d'/' -f2)" > .arch_tag; \
	else \
		echo "latest" > .arch_tag; \
	fi

dist-dev: check-arch # Build docker container (intended for developer-based manual build)
	@ARCH_TAG=$$(cat .arch_tag); \
	docker buildx inspect $(ECR_NAME_DEV) >/dev/null 2>&1 || docker buildx create --name $(ECR_NAME_DEV) --use; \
	docker buildx use $(ECR_NAME_DEV); \
	docker buildx build --platform $(CPU_ARCH) \
		--load \
	    --tag $(ECR_URL_DEV):$$ARCH_TAG \
	    --tag $(ECR_URL_DEV):make-$$ARCH_TAG \
		--tag $(ECR_URL_DEV):make-$(shell git describe --always) \
		--tag $(ECR_NAME_DEV):$$ARCH_TAG \
		.

publish-dev: dist-dev # Build, tag and push (intended for developer-based manual publish)
	@ARCH_TAG=$$(cat .arch_tag); \
	aws ecr get-login-password --region us-east-1 | docker login --username AWS --password-stdin $(ECR_URL_DEV); \
	docker push $(ECR_URL_DEV):$$ARCH_TAG; \
	docker push $(ECR_URL_DEV):make-$$ARCH_TAG; \
	docker push $(ECR_URL_DEV):make-$(shell git describe --always); \
    echo "Cleaning up dangling Docker images..."; \
    docker image prune -f --filter "dangling=true"

docker-clean: # Clean up Docker detritus
	@ARCH_TAG=$$(cat .arch_tag); \
	echo "Cleaning up Docker leftovers (containers, images, builders)"; \
	docker rmi -f $(ECR_URL_DEV):$$ARCH_TAG; \
	docker rmi -f $(ECR_URL_DEV):make-$$ARCH_TAG; \
	docker rmi -f $(ECR_URL_DEV):make-$(shell git describe --always) || true; \
    docker rmi -f $(ECR_NAME_DEV):$$ARCH_TAG || true; \
	docker buildx rm $(ECR_NAME_DEV) || true
	@rm -rf .arch_tag
