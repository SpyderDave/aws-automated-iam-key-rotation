# AWS IAM Key Auto-Rotation and Notifier Solution

A reference implementation of automated AWS IAM access key rotation with multi-account support, exemption management, and email notifications.

> **Reference implementation — not a turnkey product.** This repository is provided as an example of one way to build this solution. It is offered as-is, without warranty or support (see [LICENSE](LICENSE)). All account IDs, organization IDs, email addresses, bucket names, URLs and resource names are placeholders. Review the code, IAM permissions and email templates, adapt them to your own environment and security requirements, and test in a non-production organization (with dry-run enabled) before any production use.

## Table of Contents

- [Overview](#overview)
- [Architecture](#architecture)
- [Key Features](#key-features)
- [Components](#components)
- [Deployment](#deployment)
- [Configuration](#configuration)
- [Usage](#usage)
- [Operational Modes](#operational-modes)
- [Security](#security)
- [Troubleshooting](#troubleshooting)

## Overview

This reference implementation automates the rotation of AWS IAM access keys across an AWS Organization to comply with security best practices. It provides:

- **Automated Key Rotation**: Lifecycle management of IAM keys based on configurable rotation policies
- **Multi-Account Support**: Seamless operation across all AWS Organization accounts via cross-account IAM roles
- **Flexibility**: Supports both audit (dry-run) and enforcement (active rotation) modes
- **Exemptions**: Fine-grained control with exemption group support
- **Notifications**: Email notifications at each key lifecycle stage
- **Compliance**: Configurable rotation periods, grace periods, and warning periods

## Architecture

### High-Level System Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        AWS Organization                          │
└─────────────────────────────────────────────────────────────────┘
                                 │
                ┌────────────────┼────────────────┐
                │                │                │
        ┌───────▼────────┐  ┌────▼───────┐  ┌───▼────────────┐
        │ Primary Account │  │   Account  │  │    Account     │
        │    (Rotator)    │  │     A      │  │      B         │
        └────────────────┘  └────────────┘  └────────────────┘
```

### Execution Flow

```
CloudWatch Event (Daily 5 AM UTC)
         │
         ▼
┌──────────────────────────────┐
│  1. Account Inventory Lambda  │  ◄──── Queries AWS Organizations
│     - Lists all accounts     │       - Gets account details
│     - Retrieves tags         │       - Retrieves account tags
└──────────────────────────────┘
         │
         ▼ (Invokes asynchronously)
┌──────────────────────────────┐
│  2. Access Key Rotation      │  ◄──── For each account:
│     Lambda                   │       - Assumes cross-account role
│     - Scans IAM users        │       - Analyzes key age
│     - Evaluates key age      │       - Checks exemptions
│     - Applies rotation logic │       - Plans rotations
│     - Manages key lifecycle  │
└──────────────────────────────┘
         │
         ▼ (Async invocation)
┌──────────────────────────────┐
│  3. Notifier Lambda           │  ◄──── Sends notifications:
│     - Formats email body     │       - Audit mode: reports findings
│     - Sends via SES          │       - Enforcement: reports actions
│     - Logs delivery          │
└──────────────────────────────┘
```

### Cross-Account IAM Trust

```
Primary Account (Rotator)          Member Accounts (All targets)
┌──────────────────────┐           ┌──────────────────────┐
│ Execution Role       │           │ Assumed Role         │
│ (Lambda)             │──AssumeRole─────▶ (deployed via│
│                      │           │  StackSet)          │
└──────────────────────┘           └──────────────────────┘
```

## Key Features

### 1. **Automated Key Lifecycle Management**
- **Rotation Period**: Default 90 days before key deactivation
- **Installation Grace Period**: 7-day window to install new key (default)
- **Recovery Grace Period**: 7-day window for recovery before deletion (default)
- **Pending Warnings**: 7-day warning before each action (default)

### 2. **Dual Operating Modes**
- **Audit Mode (DryRun=True)**: Reports actions without execution
- **Enforcement Mode (DryRun=False)**: Executes rotations and deactivations

### 3. **Account-Level Control**
- Override global settings via AWS account tags: `iamRotationPolicy: Strict`
- Selective targeting: Process entire organization or specific organizational units (OUs)

### 4. **User Exemptions**
- IAM Group-based exemption management
- Users in exemption group are excluded from rotation

### 5. **Secret Manager Integration**
- Automatic secret creation for rotated keys
- Secure secret storage with per-user access policies
- Secret versioning support

### 6. **Email Notifications**
- HTML email templates (audit and enforcement modes)
- Detailed rotation reports
- Sent to account email address on file

### 7. **Force Rotation Capability**
- Trigger immediate rotation of specific keys via test events
- Useful for emergency key rotation

## Components

### 1. Account Inventory Lambda Function

**Purpose**: Discovers all AWS accounts and triggers rotation checks

**Key Responsibilities**:
- Queries AWS Organizations for all active accounts
- Supports filtering by organizational unit (OU)
- Retrieves account metadata: ID, name, email, tags
- Asynchronously invokes Access Key Rotation Lambda for each account

**Environment Variables**:
- `LambdaRotationFunction`: ARN of the rotation Lambda function
- `InventoryOU` (optional): Specific OU ID to scan (defaults to all accounts)

**Input**: CloudWatch scheduled event
**Output**: Asynchronous invocation of rotation Lambda

### 2. Access Key Rotation Lambda Function

**Purpose**: Core rotation logic - analyzes keys and manages lifecycle

**Key Responsibilities**:
- Assumes cross-account role in target account
- Lists all IAM users and access keys
- Evaluates key age and usage
- Checks exemption status
- Determines required actions
- Executes rotations (enforcement mode)
- Manages key state transitions
- Invokes notifier for reporting

**Key Modules**:
- `account_scan.py`: Key age analysis and action determination
- `sts_connection_handler.py`: Cross-account role assumption
- `key_actions.py`: Key lifecycle operations (create, deactivate, delete)
- `exemption_handler.py`: Exemption group validation
- `notification_handler.py`: Notifier invocation
- `force_rotation_handler.py`: Force rotation via test events

**Environment Variables**:
- `DryRunFlag`: Audit vs. enforcement mode
- `RotationPeriod`: Days before rotation (default: 90)
- `InstallationGracePeriod`: Days for installation (default: 7)
- `RecoveryGracePeriod`: Days for recovery before deletion (default: 7)
- `PendingActionWarnPeriod`: Days to warn in advance (default: 7)
- `IAMExemptionGroup`: Group name for exempted users
- `IAMAssumedRoleName`: Cross-account role name
- `EmailTemplateAudit`: HTML template for audit emails
- `EmailTemplateEnforce`: HTML template for enforcement emails

**Input**: Event containing account details
```json
{
  "account": "123456789012",
  "name": "account-name",
  "email": "account-owner@company.com",
  "tags": {
    "iamRotationPolicy": "Strict"
  }
}
```

**Output**: Async invocation to Notifier Lambda

### 3. Notifier Lambda Function

**Purpose**: Sends email notifications about key rotation actions

**Key Responsibilities**:
- Formats email content from templates
- Populates template variables with action details
- Sends emails via AWS SES
- Logs delivery status

**Email Templates**:
- `iam-auto-key-rotation-audit.html`: Audit mode findings
- `iam-auto-key-rotation-enforcement.html`: Enforcement actions

**Environment Variables**:
- `AdminEmail`: Sender email address
- `S3BucketName`: Bucket containing templates
- `S3BucketPrefix`: Path prefix within bucket

**Input**: Event from rotation Lambda
```json
{
  "email": "recipient@company.com",
  "subject": "IAM Key Rotation Report",
  "email_template": "iam-auto-key-rotation-enforcement.html",
  "template_values": {
    "account_id": "123456789012",
    "timestamp": "04/08/2026 05:30:00",
    "actions": "[...rotation actions...]"
  }
}
```

### 4. CloudWatch Event Rule

**Purpose**: Orchestrates the daily execution cycle

**Schedule**: `cron(0 5 ? * 1 *)` - 5 AM UTC every Monday
- Triggers Account Inventory Lambda daily
- Initiates the entire rotation workflow

## Deployment

### Prerequisites

- AWS CLI configured with appropriate credentials
- AWS SAM CLI installed (v1.0+)
- Python 3.8+
- AWS CloudFormation stack creation permissions
- AWS Organizations access

### Deployment Architecture

```
┌─────────────────────────────────┐
│ Primary Account Deployment       │
├─────────────────────────────────┤
│                                 │
│  1. Deploy Notifier Lambda      │
│     (sam-apps/notifier)         │
│                                 │
│  2. Deploy Account Inventory    │
│     Lambda (account-inventory)  │
│                                 │
│  3. Deploy Rotation Lambda      │
│     (access-key-auto-rotation)  │
│                                 │
│  4. Deploy Orchestrator CF      │
│     (iam-key-auto-rotation- │
│      and-notifier-solution)     │
│                                 │
└─────────────────────────────────┘
              │
              ▼ (StackSet)
┌─────────────────────────────────┐
│ All Organization Accounts        │
├─────────────────────────────────┤
│                                 │
│  Deploy Cross-Account Role      │
│  (iam-key-rotation-lambda-  │
│   assumed-role)                 │
│                                 │
└─────────────────────────────────┘
```

### Step-by-Step Deployment

#### 1. Set Environment Variables

```bash
# Primary account details
export PRIMARY_ACCOUNT_ID="123456789012"
export AWS_REGION="us-east-1"
export AWS_ORG_ID="o-xxxxxxxxxx"
export DRY_RUN="True"  # Start in audit mode
```

#### 2. Deploy Notifier Lambda

```bash
cd sam-apps/notifier
sam build
sam deploy \
  --template-file .aws-sam/build/template.yaml \
  --stack-name iam-rotator-notifier \
  --region $AWS_REGION \
  --parameter-overrides \
    AdminEmail="ops@company.com" \
    S3BucketName="notifier-bucket" \
    S3BucketPrefix="templates" \
  --capabilities CAPABILITY_NAMED_IAM
```

Record the Notifier Lambda ARN from outputs.

#### 3. Deploy Account Inventory Lambda

```bash
cd sam-apps/account-inventory
sam build
sam deploy \
  --template-file .aws-sam/build/template.yaml \
  --stack-name iam-rotator-account-inventory \
  --region $AWS_REGION \
  --parameter-overrides \
    LambdaRotationFunction="<rotation-lambda-arn>" \
    InventoryOU=""  # Empty = all accounts
  --capabilities CAPABILITY_NAMED_IAM
```

Record the Account Inventory Lambda ARN.

#### 4. Deploy Rotation Lambda

```bash
cd sam-apps/access-key-auto-rotation
sam build
sam deploy \
  --template-file .aws-sam/build/template.yaml \
  --stack-name iam-rotator-rotation \
  --region $AWS_REGION \
  --parameter-overrides \
    IAMRoleName="iam-key-rotation-lambda-assumed-role" \
    ExecutionRoleName="iam-key-rotation-lambda-execution-role" \
    AWSOrgID=$AWS_ORG_ID \
    DryRunFlag=$DRY_RUN \
    RotationPeriod=90 \
    InactiveBuffer=10 \
    InactivePeriod=100 \
    RecoveryGracePeriod=10 \
    NotifierLambdaFunctionArn="<notifier-lambda-arn>" \
  --capabilities CAPABILITY_NAMED_IAM
```

Record the Rotation Lambda ARN.

#### 5. Deploy Orchestration Template

```bash
aws cloudformation create-stack \
  --stack-name iam-rotator-orchestrator \
  --template-body file://templates/iam-key-auto-rotation-and-notifier-solution.yaml \
  --parameters \
    ParameterKey=AccountInventoryLambdaFunctionArn,ParameterValue="<inventory-arn>" \
    ParameterKey=AccessKeyRotateLambdaFunctionArn,ParameterValue="<rotation-arn>" \
    ParameterKey=NotifierLambdaFunctionArn,ParameterValue="<notifier-arn>" \
  --region $AWS_REGION
```

#### 6. Deploy Cross-Account Roles via StackSet

```bash
aws cloudformation create-stack-set \
  --stack-set-name iam-rotator-cross-account-roles \
  --template-body file://templates/iam-key-auto-rotation-iam-crossaccountrole.yaml \
  --parameters \
    ParameterKey=PrimaryAccountID,ParameterValue=$PRIMARY_ACCOUNT_ID \
    ParameterKey=AWSOrgID,ParameterValue=$AWS_ORG_ID \
    ParameterKey=TargetOUs,ParameterValue="ou-xxxx-yyyyyyyy,ou-xxxx-zzzzzzzz" \
  --capabilities CAPABILITY_NAMED_IAM \
  --region $AWS_REGION
```

Deploy stack instances to all target accounts:

```bash
aws cloudformation create-stack-instances \
  --stack-set-name iam-rotator-cross-account-roles \
  --accounts $AWS_ORG_ID \
  --regions $AWS_REGION \
  --deployment-preferences FailureTolerancePercentage=20,MaxConcurrentPercentage=100
```

### Pipeline Deployment

The solution is deployed via CI/CD (GitHub Actions + Sceptre) with configuration files:

- `config/example/access-key-auto-rotation.yaml`: Rotation Lambda config
- `config/example/account-inventory.yaml`: Inventory Lambda config
- `config/example/notifier.yaml`: Notifier Lambda config
- `config/example/iam-key-rotator-crossaccountrole.yaml`: Cross-account roles

## Configuration

### Global Configuration Files

#### `config/config.yaml`

```yaml
project_code: iam-key-rotator
region: us-east-1
```

### SAM Template Parameters

#### Access Key Rotation Lambda

| Parameter | Default | Description |
|-----------|---------|-------------|
| `ExecutionRoleName` | `iam-key-rotation-lambda-execution-role` | IAM role for Lambda execution |
| `IAMRoleName` | `iam-key-rotation-lambda-assumed-role` | Cross-account role name |
| `AWSOrgID` | - | AWS Organization ID (required) |
| `IAMExemptionGroup` | `IAMKeyRotationExemptionGroup` | Exemption group name |
| `EmailTemplateAudit` | `iam-auto-key-rotation-audit.html` | Audit mode email template |
| `EmailTemplateEnforce` | `iam-auto-key-rotation-enforcement.html` | Enforcement mode email template |
| `RotationPeriod` | 90 | Days before rotation (active → inactive) |
| `InactivePeriod` | 100 | Total days before key deletion |
| `InactiveBuffer` | 10 | Days between rotation and deactivation |
| `RecoveryGracePeriod` | 10 | Days between deactivation and deletion |
| `DryRunFlag` | `True` | Audit mode (true) or enforce (false) |

### Key Rotation Policy Control

#### Global Level

The `DryRunFlag` parameter controls global behavior:
- **DryRunFlag=True**: Audit mode (dry-run) - analyzes and reports without changes
- **DryRunFlag=False**: Enforcement mode (active) - executes rotations

#### Account Level (via Tags)

Override global settings using AWS account tags in Organizations:

```yaml
iamRotationPolicy: Strict  # Forces enforcement mode for this account
iamRotationPolicy: Standard  # Forces audit mode for this account
```

### Exemption Management

Users are exempted from rotation if they belong to the IAM group specified by `IAMExemptionGroup`. 

**To exempt a user**:

```bash
aws iam add-user-to-group \
  --group-name IAMKeyRotationExemptionGroup \
  --user-name service-account
```

**To re-enable rotation**:

```bash
aws iam remove-user-from-group \
  --group-name IAMKeyRotationExemptionGroup \
  --user-name service-account
```

## Usage

### Manual Execution

#### Force Audit for All Accounts

```bash
aws lambda invoke \
  --function-name Account-Inventory-Lambda \
  --region us-east-1 \
  output.json
```

#### Force Rotation for Specific User

Use test event to trigger immediate rotation:

```json
{
  "account": "123456789012",
  "name": "account-name",
  "email": "owner@company.com",
  "dryrun": false,
  "force_rotate_users": [
    "username"
  ],
  "tags": {}
}
```

### Email Notifications

The solution sends emails at key lifecycle milestones:

1. **Key Pending Rotation**: 7 days before expiration
2. **Key Rotated**: When rotation is executed
3. **Key Pending Deactivation**: 7 days before deactivation
4. **Key Deactivated**: When deactivation is executed
5. **Key Pending Deletion**: 7 days before final deletion
6. **Key Deleted**: When key is permanently deleted

Email recipients are account owners (from AWS Organizations account email).

### Monitoring & Logging

All Lambda functions log to CloudWatch:

```bash
# View rotation logs
aws logs tail /aws/lambda/IAM-Access-Key-Rotation-Function --follow

# View inventory logs
aws logs tail /aws/lambda/Account-Inventory-Lambda --follow

# View notifier logs
aws logs tail /aws/lambda/Notifier-Lambda --follow
```

### CloudWatch Metrics

Monitor via CloudWatch:
- **Duration**: Lambda execution time
- **Errors**: Function errors
- **Throttles**: Rate limiting
- **Duration**: API call latency
- **Invocations**: Execution count

## Operational Modes

### Mode 1: Audit Only (DryRunFlag=True)

In this mode, the system **analyzes but does not execute**:
- Lists all IAM users and keys
- Identifies expired/soon-to-expire keys
- Calculates rotation actions
- **Sends email reports** with audit findings
- **Does not create new keys, deactivate, or delete**

**Use Case**: Initial assessment, testing, compliance reporting

### Mode 2: Full Enforcement (DryRunFlag=False)

In this mode, the system **analyzes AND executes**:
- Identifies keys requiring rotation
- **Creates new access keys**
- **Deactivates old keys**
- **Deletes deactivated keys**
- Sends email reports with enforcement actions
- Stores new credentials in AWS Secrets Manager

**Use Case**: Production enforcement, ongoing compliance

### Mode 3: Hybrid (Account-level Override)

Global DryRunFlag can be overridden per account:

```yaml
# This account always runs in enforcement mode
iamRotationPolicy: Strict
```

```yaml
# This account always runs in audit mode
iamRotationPolicy: Standard
```

## Security

### IAM Permission Model

#### Primary Account (Rotator)

Lambda Execution Role permissions:
- **AssumeRole**: Cross-account role in member accounts
- **Lambda:InvokeFunction**: Invoke notifier Lambda
- **CloudWatch Logs**: Write execution logs

#### Member Accounts (All targets)

Cross-account assumed role permissions:
- **IAM:List***: List users, groups, keys, policies
- **IAM:GetAccessKeyLastUsed**: Access key usage data
- **IAM:CreateAccessKey**: Create new keys
- **IAM:UpdateAccessKey**: Change key status
- **IAM:DeleteAccessKey**: Delete keys
- **IAM:PutUserPolicy**: Attach inline policies
- **IAM:AttachUserPolicy**: Attach managed policies
- **SecretsManager**: Create/update secrets and set policies

### Condition-Based Access Control

Cross-account role assumption includes conditions:

```json
{
  "Effect": "Allow",
  "Action": "sts:AssumeRole",
  "Resource": "arn:aws:iam::*:role/iam-key-rotation-lambda-assumed-role",
  "Condition": {
    "StringEquals": {
      "aws:PrincipalOrgID": "o-xxxxxxxxxx"
    }
  }
}
```

This ensures:
- Only the primary account can invoke rotation
- Only accounts within the organization are processed
- No external accounts can be targeted

### Sensitive Data Protection

1. **Access Keys**: Newly created keys are immediately stored in Secrets Manager
2. **Email**: Accounts are configured with restricted SES sending
3. **Logging**: Sensitive key data is not logged
4. **Encryption**: Secrets Manager uses encryption at rest

## Troubleshooting

### Common Issues

#### 1. Cross-Account Role Assumption Fails

**Symptoms**: "User: arn:aws:iam::XXX:role/lambda-role is not authorized to perform: sts:AssumeRole"

**Solution**:
- Verify cross-account role exists in member account
- Check trust relationship includes primary account
- Validate organization condition is correct
- Confirm member account is active in organization

```bash
# Verify role exists
aws iam get-role \
  --role-name iam-key-rotation-lambda-assumed-role \
  --region us-east-1
```

#### 2. Exemption Group Not Found

**Symptoms**: "The group with name IAMKeyRotationExemptionGroup cannot be found"

**Solution**:
- Create exemption group in each account
- Verify group name matches `IAMExemptionGroup` parameter
- Ensure group exists before rotation runs

```bash
# Create exemption group
aws iam create-group --group-name IAMKeyRotationExemptionGroup
```

#### 3. Email Not Sending

**Symptoms**: Notifications not received, notifier Lambda succeeds

**Solution**:
- Verify SES sender address is verified in target region
- Check SES sending limits (sandbox vs. production)
- Confirm email template exists in S3 bucket
- Validate S3 bucket permissions for Lambda

```bash
# List verified SES addresses
aws ses list-verified-email-addresses --region us-east-1
```

#### 4. Keys Not Rotating (Dry-Run Always True)

**Symptoms**: Even with DryRunFlag=False, no keys are actually rotated

**Solution**:
- Check account tags - `iamRotationPolicy: Strict` override
- Verify DryRunFlag parameter in CloudFormation
- Review Lambda logs for tag evaluation logic
- Confirm users are not in exemption group

#### 5. Secrets Manager Failures

**Symptoms**: "AccessDenied on CreateSecret or PutSecretValue"

**Solution**:
- Verify cross-account role has SecretsManager permissions
- Check Secrets Manager resource policies
- Ensure secret name format matches configuration
- Validate encryption key permissions

### Debug Procedures

#### Check Lambda Logs

```bash
# Get last 100 log lines
aws logs tail /aws/lambda/IAM-Access-Key-Rotation-Function \
  --since 1h --max-items 100

# Stream in real-time
aws logs tail /aws/lambda/IAM-Access-Key-Rotation-Function --follow
```

#### Test Rotation Lambda Directly

```bash
aws lambda invoke \
  --function-name IAM-Access-Key-Rotation-Function \
  --payload '{
    "account": "123456789012",
    "name": "test-account",
    "email": "owner@company.com",
    "dryrun": true,
    "tags": {}
  }' \
  output.json

cat output.json
```

#### Verify CloudWatch Events

```bash
# List scheduled rules
aws events list-rules \
  --name-prefix RotationCloudWatchEvent \
  --region us-east-1

# Describe rule details
aws events describe-rule \
  --name RotationCloudWatchEventLambdaTrigger \
  --region us-east-1
```

### Performance Considerations

- **Lambda Timeout**: Set to 400 seconds (6+ minutes for large organizations)
- **Concurrent Execution**: Limit = number of accounts (asynchronous invocation)
- **API Rate Limiting**: Implement exponential backoff for AWS API calls
- **Organization Size**: 1000+ accounts may need OU-based targeting

## Documentation

### Executive & Leadership

| Document | Purpose |
|----------|---------|

### GitHub Actions & Deployment

| Document | Purpose |
|----------|---------|
| [`.github/README.md`](.github/README.md) | GitHub Actions CI/CD pipeline overview |
| [`.github/SETUP_TWO_ORGS.md`](.github/SETUP_TWO_ORGS.md) | Complete setup guide for two AWS Organizations |
| [`.github/QUICK_START_TWO_ORGS.md`](.github/QUICK_START_TWO_ORGS.md) | Quick reference and deployment examples |
| [`.github/VARIABLES_VS_SECRETS.md`](.github/VARIABLES_VS_SECRETS.md) | GitHub Actions Variables vs Secrets |

### Architecture & Design

| Document | Purpose |
|----------|---------|
| [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) | System architecture and component details |
| [`docs/DESIGN.md`](docs/DESIGN.md) | Design decisions and rationale |
| [`docs/IMPLEMENTATION.md`](docs/IMPLEMENTATION.md) | Implementation details and deployment |
| [`docs/OPERATIONS.md`](docs/OPERATIONS.md) | Operations and maintenance guide |

### Configuration & Implementation

| Document | Purpose |
|----------|---------|
| [`docs/ACCOUNT_TAGGING.md`](docs/ACCOUNT_TAGGING.md) | AWS account tag configuration and control |

### Support Resources


---

**Last Updated**: 2026-08-04  
**Version**: 2.0  
**Status**: Production
