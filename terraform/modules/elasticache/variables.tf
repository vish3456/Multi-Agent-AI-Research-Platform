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
  description = "ECS Task security group"
}

variable "node_type" {
  type        = string
  default     = "cache.t4g.micro"
}
