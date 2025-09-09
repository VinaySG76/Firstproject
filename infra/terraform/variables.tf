variable "aws_region" {
  description = "AWS Region"
  type        = string
  default     = "ap-south-1"  # Mumbai
}

variable "s3_bucket_name" {
  description = "S3 Bucket for user file storage"
  type        = string
}

variable "ec2_instance_type" {
  description = "EC2 instance type for app server"
  type        = string
  default     = "t3.micro"
}

variable "ec2_key_name" {
  description = "Existing EC2 key pair name"
  type        = string
}

variable "rds_username" {
  description = "RDS MySQL username"
  type        = string
  default     = "admin"
}

variable "rds_password" {
  description = "RDS MySQL password"
  type        = string
  sensitive   = true
}

variable "rds_db_name" {
  description = "Database name"
  type        = string
  default     = "cloud_drive"
}
