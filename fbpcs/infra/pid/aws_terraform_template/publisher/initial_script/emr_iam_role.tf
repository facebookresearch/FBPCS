resource "aws_iam_role" "mrpid_publisher_emr_role" {
  name = "mrpid-publisher-emr-role-${var.pce_instance_id}"

  assume_role_policy = <<POLICY
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "Service": "elasticmapreduce.amazonaws.com"
      },
      "Action": "sts:AssumeRole"
    }
  ]
}
POLICY
}

resource "aws_iam_role_policy_attachment" "mrpid_emr_role_attach" {
  role = aws_iam_role.mrpid_publisher_emr_role.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonElasticMapReduceRole"
}

# make sure the IAM service-linked role exists, iganore error if the role already exists
resource "null_resource" "mrpid_create_emr_service_linked_role" {
  provisioner "local-exec" {
    command = "aws iam create-service-linked-role --aws-service-name elasticmapreduce.amazonaws.com"
    on_failure = continue
  }
}
