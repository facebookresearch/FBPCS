variable "region" {
  description = "region of the aws resources"
  default     = "us-west-2"
}

variable "app_data_input_bucket" {
  description = "S3 bucket for advertisers to upload app data and necessary python scripts"
  default     = ""
}

variable "lambda_trigger_s3_key" {
  description = "Source S3 key for lambda trigger function used in semi-automated data ingestion"
  default     = ""
}

variable "tag_postfix" {
  description = "the postfix to append after a resource name or tag"
  default     = ""
}

variable "aws_account_id" {
  description = "your aws account id, that's used to read encrypted S3 files"
  default     = ""
}
