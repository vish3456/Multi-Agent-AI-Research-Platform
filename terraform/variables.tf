variable "aws_region" {
  type        = string
  description = "AWS region for deployment"
  default     = "us-east-1"
}

variable "environment" {
  type        = string
  description = "Environment name (e.g. dev, prod)"
  default     = "production"
}

variable "project_name" {
  type        = string
  description = "Project name prefix"
  default     = "multi-agent-research"
}

variable "vpc_cidr" {
  type        = string
  description = "CIDR block for VPC"
  default     = "10.0.0.0/16"
}

variable "app_port" {
  type        = number
  description = "Port exposed by application"
  default     = 8000
}

variable "red_team_port" {
  type        = number
  description = "Port exposed by red team container"
  default     = 8001
}

variable "db_name" {
  type        = string
  description = "PostgreSQL database name"
  default     = "research_platform"
}

variable "db_username" {
  type        = string
  description = "PostgreSQL admin username"
  default     = "postgres_admin"
}

variable "db_instance_class" {
  type        = string
  description = "RDS instance class"
  default     = "db.t4g.micro"
}

variable "redis_node_type" {
  type        = string
  description = "ElastiCache Redis node type"
  default     = "cache.t4g.micro"
}
