provider "aws" {
  region = var.aws_region
}

# 1. VPC Module
module "vpc" {
  source       = "./modules/vpc"
  project_name = var.project_name
  environment  = var.environment
  vpc_cidr     = var.vpc_cidr
}

# 2. IAM Module
module "iam" {
  source       = "./modules/iam"
  project_name = var.project_name
  environment  = var.environment
}

# 3. Monitoring Module
module "monitoring" {
  source       = "./modules/monitoring"
  project_name = var.project_name
  environment  = var.environment
}

# 4. Secrets Module
module "secrets" {
  source       = "./modules/secrets"
  project_name = var.project_name
  environment  = var.environment
}

# 5. Bedrock Guardrails Module
module "bedrock" {
  source       = "./modules/bedrock"
  project_name = var.project_name
  environment  = var.environment
}

# 6. ECR Repositories Module
module "ecr" {
  source       = "./modules/ecr"
  project_name = var.project_name
  environment  = var.environment
}

# 7. Application Load Balancer Module
module "alb" {
  source            = "./modules/alb"
  project_name      = var.project_name
  environment       = var.environment
  vpc_id            = module.vpc.vpc_id
  public_subnet_ids = module.vpc.public_subnet_ids
  app_port          = var.app_port
  red_team_port     = var.red_team_port
}

# 8. ECS Cluster and Services Module
module "ecs" {
  source                    = "./modules/ecs"
  project_name              = var.project_name
  environment               = var.environment
  aws_region                = var.aws_region
  vpc_id                    = module.vpc.vpc_id
  private_subnet_ids        = module.vpc.private_subnet_ids
  alb_security_group_id     = module.alb.alb_security_group_id
  app_target_group_arn      = module.alb.app_target_group_arn
  red_team_target_group_arn = module.alb.red_team_target_group_arn
  execution_role_arn        = module.iam.execution_role_arn
  task_role_arn             = module.iam.task_role_arn
  app_image                 = "${module.ecr.app_repository_url}:latest"
  tensorzero_image          = "${module.ecr.tensorzero_repository_url}:latest"
  pyrit_image               = "${module.ecr.pyrit_repository_url}:latest"
  app_log_group             = module.monitoring.app_log_group_name
  tensorzero_log_group      = module.monitoring.tensorzero_log_group_name
  pyrit_log_group           = module.monitoring.pyrit_log_group_name
  secrets_arn               = module.secrets.secret_arn
  redis_url                 = module.elasticache.redis_url
  database_url              = module.rds.database_url
  guardrail_id              = module.bedrock.guardrail_id
  guardrail_version         = module.bedrock.guardrail_version
  app_port                  = var.app_port
  red_team_port             = var.red_team_port
}

# 9. RDS PostgreSQL 15 Module
module "rds" {
  source                = "./modules/rds"
  project_name          = var.project_name
  environment           = var.environment
  vpc_id                = module.vpc.vpc_id
  database_subnet_ids   = module.vpc.database_subnet_ids
  ecs_security_group_id = module.ecs.ecs_tasks_security_group_id
  db_name               = var.db_name
  db_username           = var.db_username
  db_password           = module.secrets.generated_db_password
  db_instance_class     = var.db_instance_class
}

# 10. Redis ElastiCache Module
module "elasticache" {
  source                = "./modules/elasticache"
  project_name          = var.project_name
  environment           = var.environment
  vpc_id                = module.vpc.vpc_id
  database_subnet_ids   = module.vpc.database_subnet_ids
  ecs_security_group_id = module.ecs.ecs_tasks_security_group_id
  node_type             = var.redis_node_type
}

# 11. EventBridge Schedule Module
module "eventbridge" {
  source                      = "./modules/eventbridge"
  project_name                = var.project_name
  environment                 = var.environment
  ecs_cluster_arn             = "arn:aws:ecs:${var.aws_region}:${module.ecs.cluster_name}"
  pyrit_task_definition_arn   = module.ecs.pyrit_task_definition_arn
  private_subnet_ids          = module.vpc.private_subnet_ids
  ecs_tasks_security_group_id = module.ecs.ecs_tasks_security_group_id
}
