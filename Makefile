SHELL=/bin/bash
DATETIME:=$(shell date -u +%Y%m%dT%H%M%SZ)

ECR_NAME_DEV:=browsertrix-harvester-dev
ECR_URL_DEV:=222053980223.dkr.ecr.us-east-1.amazonaws.com/browsertrix-harvester-dev

CPU_ARCH ?= $(shell cat .aws-architecture 2>/dev/null || echo "linux/amd64")

help: # Preview Makefile commands
	@awk 'BEGIN { FS = ":.*#"; print "Usage:  make <target>\n\nTargets:" } \
/^[-_[:alpha:]]+:.?*#/ { printf "  %-15s%s\n", $$1, $$2 }' $(MAKEFILE_LIST)

# ensure OS binaries aren't called if naming conflict with Make recipes
.PHONY: help install venv update test coveralls lint lint-fix security check-arch dist-dev publish-dev docker-clean harvester docker-build docker-shell docker-test-run run-harvest-local run-harvest-dev run-harvest-stage parse-url-content-local

##############################################
# Python Environment and Dependency commands
##############################################

install: .venv .git/hooks/pre-commit .git/hooks/pre-push # Install Python dependencies and create virtual environment if not exists
	uv sync --dev

.venv: # Creates virtual environment if not found
	@echo "Creating virtual environment at .venv..."
	uv venv .venv

.git/hooks/pre-commit: # Sets up pre-commit commit hooks if not setup
	@echo "Installing pre-commit commit hooks..."
	uv run pre-commit install --hook-type pre-commit

.git/hooks/pre-push: # Sets up pre-commit push hooks if not setup
	@echo "Installing pre-commit push hooks..."
	uv run pre-commit install --hook-type pre-push

venv: .venv # Create the Python virtual environment

update: # Update Python dependencies
	uv lock --upgrade
	uv sync --dev

######################
# Unit test commands
######################

test: # Run tests and print a coverage report
	uv run coverage run --source=harvester -m pytest -vv
	uv run coverage report -m

coveralls: test # Write coverage data to an LCOV report
	uv run coverage lcov -o ./coverage/lcov.info

####################################
# Code linting and formatting
####################################

lint: # Run linting, alerts only, no code changes
	uv run ruff format --diff
	uv run mypy .
	uv run ruff check .

lint-fix: # Run linting, auto fix behaviors where supported
	uv run ruff format .
	uv run ruff check --fix .

security: # Run security / vulnerability checks
	uv run pip-audit

###############################################
# CLI commands
###############################################

harvester: # CLI without any arguments, utilizing uv script entrypoint
	uv run harvester

###############################################
# Docker image, ECR, and Lambda Management
###############################################

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

##########
# Docker
##########

docker-build: # Build local image for testing
	docker buildx build --load -t $(ECR_NAME_DEV):latest .

docker-shell: # Shell into local container for testing
	docker run -it -v $(PWD)/output/crawls:/crawls browsertrix-harvester-dev:latest docker-shell

docker-test-run: # Test local docker container
	docker run -it -v $(PWD)/output/crawls:/crawls browsertrix-harvester-dev:latest

####################
# Testing commands
####################

parse-url-content-local: # Test local URL content parsing
	uv run harvester parse-url-content \
	--wacz-input-file="tests/fixtures/example.wacz" \
	--url="https://example.com/hello-world"