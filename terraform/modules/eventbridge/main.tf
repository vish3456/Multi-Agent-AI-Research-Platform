# IAM Role allowing EventBridge to invoke ECS RunTask
data "aws_iam_policy_document" "events_assume" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["events.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "eventbridge_ecs" {
  name               = "${var.project_name}-eventbridge-ecs-role"
  assume_role_policy = data.aws_iam_policy_document.events_assume.json

  tags = {
    Name        = "${var.project_name}-eventbridge-ecs-role"
    Environment = var.environment
  }
}

resource "aws_iam_policy" "eventbridge_run_task" {
  name = "${var.project_name}-eventbridge-run-task"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect   = "Allow"
        Action   = ["ecs:RunTask"]
        Resource = [var.pyrit_task_definition_arn]
      },
      {
        Effect   = "Allow"
        Action   = ["iam:PassRole"]
        Resource = ["*"]
      }
    ]
  })
}

resource "aws_iam_role_policy_attachment" "eventbridge_run_task_attach" {
  role       = aws_iam_role.eventbridge_ecs.name
  policy_arn = aws_iam_policy.eventbridge_run_task.arn
}

# Scheduled Rule: Mondays at 2:00 AM UTC
resource "aws_cloudwatch_event_rule" "weekly_pyrit" {
  name                = "${var.project_name}-weekly-redteam-eval"
  description         = "Trigger PyRIT security eval every Monday at 2am UTC"
  schedule_expression = "cron(0 2 ? * MON *)"

  tags = {
    Name        = "${var.project_name}-weekly-redteam-eval"
    Environment = var.environment
  }
}

# Target: ECS RunTask
resource "aws_cloudwatch_event_target" "pyrit_target" {
  rule     = aws_cloudwatch_event_rule.weekly_pyrit.name
  arn      = var.ecs_cluster_arn
  role_arn = aws_iam_role.eventbridge_ecs.arn

  ecs_target {
    task_count          = 1
    task_definition_arn = var.pyrit_task_definition_arn
    launch_type         = "FARGATE"

    network_configuration {
      subnets          = var.private_subnet_ids
      security_groups  = [var.ecs_tasks_security_group_id]
      assign_public_ip = false
    }
  }
}
