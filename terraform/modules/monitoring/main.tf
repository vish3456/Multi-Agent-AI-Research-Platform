locals {
  services = ["app", "tensorzero", "pyrit"]
}

resource "aws_cloudwatch_log_group" "logs" {
  for_each          = toset(locals.services)
  name              = "/ecs/${var.project_name}-${each.key}"
  retention_in_days = 7

  tags = {
    Name        = "${var.project_name}-${each.key}-logs"
    Environment = var.environment
  }
}
