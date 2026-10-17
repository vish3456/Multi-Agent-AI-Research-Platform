output "cluster_id" {
  value = aws_ecs_cluster.main.id
}

output "cluster_name" {
  value = aws_ecs_cluster.main.name
}

output "ecs_tasks_security_group_id" {
  value = aws_security_group.ecs_tasks.id
}

output "app_service_name" {
  value = aws_ecs_service.app.name
}

output "pyrit_task_definition_arn" {
  value = aws_ecs_task_definition.pyrit.arn
}
