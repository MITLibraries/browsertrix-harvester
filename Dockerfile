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

# Install Python
RUN apt-get install -y python3.12 python3.12-venv python3.12-dev

# Install pip for Python
RUN apt-get install -y python3-pip

# Create and activate a virtual environment
RUN python3 -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Install pip and pipenv within the virtual environment
RUN pip install --upgrade pip \
    && pip install pipenv

# NOTE: /app is already used by browsertrix-crawler
# Setup python virtual environment
WORKDIR /browsertrix-harvester
COPY Pipfile /browsertrix-harvester/Pipfile
RUN pipenv install --python 3.12

# Copy full browstrix-harvester app
COPY pyproject.toml /browsertrix-harvester/
COPY docker-entrypoint.sh /browsertrix-harvester/
COPY harvester/ /browsertrix-harvester/harvester/
COPY tests/ /browsertrix-harvester/tests/

ENTRYPOINT ["/browsertrix-harvester/docker-entrypoint.sh"]