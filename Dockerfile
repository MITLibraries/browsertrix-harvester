# extend the browsertrix-crawler docker image
FROM webrecorder/browsertrix-crawler:latest

# Set environment variables to ensure non-interactive installation (no prompt)
ENV DEBIAN_FRONTEND=noninteractive

# install some OS packages
RUN apt-get update \
    && apt-get install -y unzip

# Update and install software-properties-common to get add-apt-repository
RUN apt-get update \
    && apt-get install -y software-properties-common \
    && add-apt-repository ppa:deadsnakes/ppa \
    && apt-get update

# Install Python 3.11
RUN apt-get install -y python3.11 python3.11-venv python3.11-dev

# Install pip for Python 3.11
RUN apt-get install -y python3-pip

# Upgrade pip and install pipenv
RUN pip3 install --upgrade pip \
    && pip3 install pipenv

# NOTE: /app is already used by browsertrix-crawler
# Setup python virtual environment
WORKDIR /btxharvest
COPY Pipfile /btxharvest/Pipfile
RUN pipenv install --python 3.11

# Copy full browstrix-harvester app
COPY pyproject.toml /btxharvest/
COPY docker-entrypoint.sh /btxharvest/
COPY browsertrix_harvester/ /btxharvest/browsertrix_harvester/
COPY tests/ /btxharvest/tests/

ENTRYPOINT ["/btxharvest/docker-entrypoint.sh"]