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

# CLI commands
shell:
	pipenv run harvest-dockerized shell

# Docker commands
dist-local:
	docker build -t $(ECR_NAME_DEV):latest .
