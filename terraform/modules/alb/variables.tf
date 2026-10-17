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

variable "public_subnet_ids" {
  type        = list(string)
  description = "Public subnet IDs for ALB placement"
}

variable "app_port" {
  type        = number
  description = "Port exposed by application task"
  default     = 8000
}

variable "red_team_port" {
  type        = number
  description = "Port exposed by red team container"
  default     = 8001
}
