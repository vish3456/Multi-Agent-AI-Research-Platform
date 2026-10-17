variable "project_name" {
  type        = string
  description = "Project name prefix"
}

variable "environment" {
  type        = string
  description = "Deployment environment"
}

variable "ecs_cluster_arn" {
  type        = string
}

variable "pyrit_task_definition_arn" {
  type        = string
}

variable "private_subnet_ids" {
  type        = list(string)
}

variable "ecs_tasks_security_group_id" {
  type        = string
}
