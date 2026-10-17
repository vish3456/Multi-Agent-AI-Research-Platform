# Security group for ECS tasks
resource "aws_security_group" "ecs_tasks" {
  name        = "${var.project_name}-ecs-tasks-sg"
  description = "Allow inbound traffic from ALB only"
  vpc_id      = var.vpc_id

  ingress {
    description     = "App port from ALB"
    from_port       = var.app_port
    to_port         = var.app_port
    protocol        = "tcp"
    security_groups = [var.alb_security_group_id]
  }

  ingress {
    description     = "Red team port from ALB"
    from_port       = var.red_team_port
    to_port         = var.red_team_port
    protocol        = "tcp"
    security_groups = [var.alb_security_group_id]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Name        = "${var.project_name}-ecs-tasks-sg"
    Environment = var.environment
  }
}

resource "aws_ecs_cluster" "main" {
  name = "${var.project_name}-cluster"

  setting {
    name  = "containerInsights"
    value = "enabled"
  }

  tags = {
    Name        = "${var.project_name}-cluster"
    Environment = var.environment
  }
}

# App Task Definition (App + TensorZero sidecar)
resource "aws_ecs_task_definition" "app" {
  family                   = "${var.project_name}-app-task"
  network_mode             = "awsvpc"
  requires_compatibilities = ["FARGATE"]
  cpu                      = "1024"
  memory                   = "2048"
  execution_role_arn       = var.execution_role_arn
  task_role_arn            = var.task_role_arn

  container_definitions = jsonencode([
    {
      name      = "app"
      image     = var.app_image
      essential = true
      portMappings = [
        {
          containerPort = var.app_port
          hostPort      = var.app_port
          protocol      = "tcp"
        }
      ]
      environment = [
        { name = "APP_PORT", value = tostring(var.app_port) },
        { name = "REDIS_URL", value = var.redis_url },
        { name = "DATABASE_URL", value = var.database_url },
        { name = "GUARDRAIL_ID", value = var.guardrail_id },
        { name = "GUARDRAIL_VERSION", value = var.guardrail_version },
        { name = "AWS_REGION", value = var.aws_region },
        { name = "TENSORZERO_URL", value = "http://localhost:3000" },
        { name = "EMBEDDING_MODEL", value = "all-MiniLM-L6-v2" },
        { name = "EMBEDDING_DIM", value = "384" }
      ]
      secrets = [
        { name = "API_KEY", valueFrom = "${var.secrets_arn}:API_KEY::" },
        { name = "OPENAI_API_KEY", valueFrom = "${var.secrets_arn}:OPENAI_API_KEY::" },
        { name = "GROQ_API_KEY", valueFrom = "${var.secrets_arn}:GROQ_API_KEY::" },
        { name = "LANGSMITH_API_KEY", valueFrom = "${var.secrets_arn}:LANGSMITH_API_KEY::" }
      ]
      logConfiguration = {
        logDriver = "awslogs"
        options = {
          "awslogs-group"         = var.app_log_group
          "awslogs-region"        = var.aws_region
          "awslogs-stream-prefix" = "app"
        }
      }
    },
    {
      name      = "tensorzero"
      image     = var.tensorzero_image
      essential = true
      portMappings = [
        {
          containerPort = 3000
          hostPort      = 3000
          protocol      = "tcp"
        }
      ]
      secrets = [
        { name = "OPENAI_API_KEY", valueFrom = "${var.secrets_arn}:OPENAI_API_KEY::" },
        { name = "GROQ_API_KEY", valueFrom = "${var.secrets_arn}:GROQ_API_KEY::" }
      ]
      logConfiguration = {
        logDriver = "awslogs"
        options = {
          "awslogs-group"         = var.tensorzero_log_group
          "awslogs-region"        = var.aws_region
          "awslogs-stream-prefix" = "tensorzero"
        }
      }
    }
  ])

  tags = {
    Name        = "${var.project_name}-app-task"
    Environment = var.environment
  }
}

# Red Team Task Definition
resource "aws_ecs_task_definition" "pyrit" {
  family                   = "${var.project_name}-pyrit-task"
  network_mode             = "awsvpc"
  requires_compatibilities = ["FARGATE"]
  cpu                      = "512"
  memory                   = "1024"
  execution_role_arn       = var.execution_role_arn
  task_role_arn            = var.task_role_arn

  container_definitions = jsonencode([
    {
      name      = "pyrit"
      image     = var.pyrit_image
      essential = true
      portMappings = [
        {
          containerPort = var.red_team_port
          hostPort      = var.red_team_port
          protocol      = "tcp"
        }
      ]
      environment = [
        { name = "TARGET_URL", value = "http://localhost:8000" }
      ]
      secrets = [
        { name = "API_KEY", valueFrom = "${var.secrets_arn}:API_KEY::" }
      ]
      logConfiguration = {
        logDriver = "awslogs"
        options = {
          "awslogs-group"         = var.pyrit_log_group
          "awslogs-region"        = var.aws_region
          "awslogs-stream-prefix" = "pyrit"
        }
      }
    }
  ])

  tags = {
    Name        = "${var.project_name}-pyrit-task"
    Environment = var.environment
  }
}

# App Service with circuit breaker
resource "aws_ecs_service" "app" {
  name            = "${var.project_name}-app-service"
  cluster         = aws_ecs_cluster.main.id
  task_definition = aws_ecs_task_definition.app.arn
  desired_count   = 2
  launch_type     = "FARGATE"

  network_configuration {
    subnets          = var.private_subnet_ids
    security_groups  = [aws_security_group.ecs_tasks.id]
    assign_public_ip = false
  }

  load_balancer {
    target_group_arn = var.app_target_group_arn
    container_name   = "app"
    container_port   = var.app_port
  }

  deployment_circuit_breaker {
    enable   = true
    rollback = true
  }

  tags = {
    Name        = "${var.project_name}-app-service"
    Environment = var.environment
  }
}

# Auto-Scaling Target for App Service
resource "aws_appautoscaling_target" "app" {
  max_capacity       = 6
  min_capacity       = 2
  resource_id        = "service/${aws_ecs_cluster.main.name}/${aws_ecs_service.app.name}"
  scalable_dimension = "ecs:service:DesiredCount"
  service_namespace  = "ecs"
}

resource "aws_appautoscaling_policy" "cpu" {
  name               = "${var.project_name}-cpu-autoscaling"
  policy_type        = "TargetTrackingScaling"
  resource_id        = aws_appautoscaling_target.app.resource_id
  scalable_dimension = aws_appautoscaling_target.app.scalable_dimension
  service_namespace  = aws_appautoscaling_target.app.service_namespace

  target_tracking_scaling_policy_configuration {
    predefined_metric_specification {
      predefined_metric_type = "ECSServiceAverageCPUUtilization"
    }
    target_value       = 70.0
    scale_in_cooldown  = 300
    scale_out_cooldown = 60
  }
}
