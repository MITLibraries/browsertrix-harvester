# extract date
export CURRENT_DATE=$(date +"%Y-%m-%d")
export CRAWL_NAME=test-harvest-ecs-$CURRENT_DATE
echo "Invoking test crawl as ECS task in Dev1 named: $CRAWL_NAME"

# invoke ECS task
aws ecs run-task \
--cluster timdex-dev \
--task-definition timdex-browsertrixharvester-dev \
--launch-type="FARGATE" \
--region us-east-1 \
--network-configuration '{"awsvpcConfiguration": {"subnets": ["subnet-0488e4996ddc8365b","subnet-022e9ea19f5f93e65"], "securityGroups": ["sg-044033bf5f102c544"]}}' \
--overrides '{"containerOverrides": [ {"name":"browsertrix-harvester", "command": ["--verbose", "harvest", "--crawl-name", "'"$CRAWL_NAME"'", "--config-yaml-file", "/browsertrix-harvester/tests/fixtures/lib-website-homepage.yaml", "--metadata-output-file", "s3://timdex-extract-dev-222053980223/librarywebsite/'"$CRAWL_NAME"'.xml", "--wacz-output-file", "s3://timdex-extract-dev-222053980223/librarywebsite/'"$CRAWL_NAME"'.wacz", "--num-workers", "2"]}]}'