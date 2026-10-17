resource "random_password" "api_key" {
  length  = 32
  special = false
}

resource "random_password" "db_password" {
  length  = 24
  special = false
}

resource "aws_secretsmanager_secret" "app_secrets" {
  name                    = "${var.project_name}-app-secrets"
  recovery_window_in_days = 0

  tags = {
    Name        = "${var.project_name}-app-secrets"
    Environment = var.environment
  }
}

resource "aws_secretsmanager_secret_version" "app_secrets_val" {
  secret_id = aws_secretsmanager_secret.app_secrets.id
  secret_string = jsonencode({
    API_KEY          = random_password.api_key.result
    DB_PASSWORD      = random_password.db_password.result
    OPENAI_API_KEY   = "placeholder-replace-in-console"
    GROQ_API_KEY     = "placeholder-replace-in-console"
    LANGSMITH_API_KEY = "placeholder-replace-in-console"
  })
}
