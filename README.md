# IAM Key Auto-Rotation and Notifier Solution

## Overview
This repository provides an automated solution for rotating IAM access keys and notifying users. It includes AWS Lambda functions, CloudFormation templates, and configuration files.

## Features
- Automated IAM access key rotation.
- Notification system for key expiration and compliance.
- AWS Lambda functions to handle key management and notifications.
- CloudFormation templates for easy deployment.
- Unit tests to validate functionality.

## Repository Structure
```
├── config/                 # Configuration files
├── sam-apps/               # Serverless applications (Lambda functions)
│   ├── access_key_auto_rotation/
│   ├── account_inventory/
│   ├── notifier/
│   │   ├── email-template/ # Email templates for notifications
├── templates/              # CloudFormation templates
├── unit-test/              # Sample test cases
```

## Deployment
### Prerequisites
- AWS CLI installed and configured
- AWS SAM CLI installed
- Python 3.x

### Deployment Process
Deploy with your CI/CD tool of choice (e.g. via StackSets/CloudFormation and AWS SAM). Pipeline variables referenced in `config/` (`bamboo_*`) must be supplied by your CI system.


## Attribution and License

This project is derived from [aws-samples/aws-iam-access-key-auto-rotation](https://github.com/aws-samples/aws-iam-access-key-auto-rotation) (MIT-0, Copyright Amazon.com, Inc. or its affiliates). See [NOTICE](NOTICE).

Licensed under the MIT No Attribution license. See [LICENSE](LICENSE).
