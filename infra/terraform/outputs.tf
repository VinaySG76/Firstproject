output "s3_bucket_name" {
  value = aws_s3_bucket.user_files.bucket
}

output "ec2_public_ip" {
  value = aws_instance.app_server.public_ip
}

output "rds_endpoint" {
  value = aws_db_instance.mysql.endpoint
}
