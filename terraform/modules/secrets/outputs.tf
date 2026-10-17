output "secret_arn" {
  value = aws_secretsmanager_secret.app_secrets.arn
}

output "secret_name" {
  value = aws_secretsmanager_secret.app_secrets.name
}

output "generated_db_password" {
  value     = random_password.db_password.result
  sensitive = true
}

output "generated_api_key" {
  value     = random_password.api_key.result
  sensitive = true
}
