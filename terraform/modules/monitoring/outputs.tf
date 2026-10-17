output "app_log_group_name" {
  value = aws_cloudwatch_log_group.logs["app"].name
}

output "tensorzero_log_group_name" {
  value = aws_cloudwatch_log_group.logs["tensorzero"].name
}

output "pyrit_log_group_name" {
  value = aws_cloudwatch_log_group.logs["pyrit"].name
}
