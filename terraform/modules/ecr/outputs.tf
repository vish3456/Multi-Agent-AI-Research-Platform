output "app_repository_url" {
  value = aws_ecr_repository.repos["app"].repository_url
}

output "tensorzero_repository_url" {
  value = aws_ecr_repository.repos["tensorzero"].repository_url
}

output "pyrit_repository_url" {
  value = aws_ecr_repository.repos["pyrit"].repository_url
}
