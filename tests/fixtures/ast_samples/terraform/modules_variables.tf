variable "region" {
  type        = string
  default     = "us-east-1"
  description = "AWS region"
}

variable "instance_count" {
  type    = number
  default = 2
}

output "instance_ids" {
  value       = aws_instance.web[*].id
  description = "IDs of created instances"
}

locals {
  common_tags = {
    Environment = "dev"
    Project     = "example"
  }
}
