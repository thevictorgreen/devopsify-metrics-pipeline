# devopsify-metrics-pipeline
=========

AWS Cloudformation Template which creates a data pipeline comprising Kinesis Data Stream, Lambda Function, and DynamoDB Table

Requirements
------------

1: Upload lambda_function.zip to an S3 Bucket

2: Update the following 5 parameters after uploading the lambda_function.zip file
   with the appropriate values
_S3-BUCKET-NAME_
_S3-BUCKET-NAME-AND-PATH_
_S3-OBJECT-VERSION_
_SECURITY-GROUPS_
_SUBNET-IDS_

3: Deploy the template via AWS Cloudformation
