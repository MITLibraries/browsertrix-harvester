### This is the Terraform-generated header for browsertrix-harvester-dev. If  ###
###   this is a Lambda repo, uncomment the FUNCTION line below  ###
###   and review the other commented lines in the document.     ###
ECR_NAME_DEV:=browsertrix-harvester-dev
ECR_URL_DEV:=222053980223.dkr.ecr.us-east-1.amazonaws.com/browsertrix-harvester-dev
### End of Terraform-generated header                            ###
SHELL=/bin/bash
DATETIME:=$(shell date -u +%Y%m%dT%H%M%SZ)

### Dependency commands ###
install: ## Install dependencies and CLI app
	pipenv install --dev

update: install ## Update all Python dependencies
	pipenv clean
	pipenv update --dev

### Test commands ###
test: ## Run tests and print a coverage report
	pipenv run coverage run --source=browsertrix_harvester -m pytest -vv
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

# CLI commands
shell:
	pipenv run btrixharvest-dockerized shell

# Docker commands
build-docker:
	docker build -t $(ECR_NAME_DEV):latest .

# Test crawl commands
# local docker container crawl
test-harvest-local:
	pipenv run btrixharvest-dockerized --verbose harvest \
	--crawl-name="homepage" \
	--config-yaml-file="/btrixharvest/tests/fixtures/lib-website-homepage.yaml" \
	--metadata-output-file="/crawls/collections/homepage/homepage.xml" \
	--num-workers 4 \
	--btrix-args-json='{"--maxPageLimit":"15"}'

# remote ecs task crawl in Dev1
test-harvest-ecs:
	bin/test-harvest-ecs.sh

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
