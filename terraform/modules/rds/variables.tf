variable "project_name" {
  type        = string
  description = "Project name prefix"
}

variable "environment" {
  type        = string
  description = "Deployment environment"
}

variable "vpc_id" {
  type        = string
  description = "VPC ID"
}

variable "database_subnet_ids" {
  type        = list(string)
  description = "Database subnets"
}

variable "ecs_security_group_id" {
  type        = string
  description = "ECS Task security group permitted to access database"
}

variable "db_name" {
  type        = string
  default     = "research_platform"
}

variable "db_username" {
  type        = string
  default     = "postgres_admin"
}

variable "db_password" {
  type        = string
  sensitive   = true
}

variable "db_instance_class" {
  type        = string
  default     = "db.t4g.micro"
}
