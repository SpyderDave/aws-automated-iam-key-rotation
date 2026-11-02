# Quick Start Guide

A fast-track guide for deploying and operating the IAM Key Rotation solution.

## 5-Minute Overview

**What This Does**: Automatically rotates AWS IAM access keys across your entire AWS Organization on a configurable schedule to maintain security compliance.

**How It Works**:

```
1. CloudWatch triggers daily (5 AM UTC)
   ↓
2. Account Inventory Lambda lists all accounts
   ↓
3. For each account, Rotation Lambda:
   - Assumes cross-account role
   - Scans IAM keys for age
   - Creates new keys
   - Deactivates old keys
   ↓
4. Notifier Lambda sends emails to account owners
```

**Key Features**:
- ✅ Multi-account support (100+ accounts)
- ✅ Audit mode (test without changes)
- ✅ Enforcement mode (automatic rotation)
- ✅ User exemptions (for service accounts)
- ✅ Email notifications
- ✅ Secrets Manager integration
- ✅ Compliance logging

## Pre-Deployment Checklist

```bash
# 1. Verify prerequisites
aws organizations describe-organization
aws sts get-caller-identity

# 2. Collect IDs
ORG_ID=$(aws organizations describe-organization --query 'Organization.Id' --output text)
PRIMARY_ACCOUNT=$(aws sts get-caller-identity --query 'Account' --output text)
echo "ORG_ID=$ORG_ID"
echo "PRIMARY_ACCOUNT=$PRIMARY_ACCOUNT"

# 3. Verify SES
aws ses list-verified-email-addresses --region us-east-1
```

## Quick Deploy (15 minutes)

### 1. Set Environment Variables

```bash
export ORG_ID="o-xxxxxxxxxx"
export PRIMARY_ACCOUNT="123456789012"
export ADMIN_EMAIL="ops@company.com"
export AWS_REGION="us-east-1"
export DRY_RUN="True"  # Start in audit mode
```

### 2. Create S3 Bucket for Templates

```bash
aws s3 mb s3://iam-rotation-templates --region $AWS_REGION

# Upload email templates
cd sam-apps/notifier/email-template
aws s3 sync . s3://iam-rotation-templates/ --region $AWS_REGION
cd ../../../
```

### 3. Deploy All Lambdas (via SAM)

```bash
# Deploy in order: Notifier → Inventory → Rotation

# Notifier
cd sam-apps/notifier && sam build && sam deploy \
  --stack-name iam-rotator-notifier \
  --parameter-overrides \
    AdminEmail=$ADMIN_EMAIL \
    S3BucketName=iam-rotation-templates \
    S3BucketPrefix="/" \
  --capabilities CAPABILITY_NAMED_IAM \
  --no-confirm-changeset && cd ../..

# Capture Notifier ARN
NOTIFIER_ARN=$(aws cloudformation describe-stacks \
  --stack-name iam-rotator-notifier \
  --query 'Stacks[0].Outputs[0].OutputValue' --output text)

# Inventory
cd sam-apps/account-inventory && sam build && sam deploy \
  --stack-name iam-rotator-inventory \
  --parameter-overrides \
    LambdaRotationFunction="arn:aws:lambda:$AWS_REGION:$PRIMARY_ACCOUNT:function:IAM-Access-Key-Rotation-Function" \
  --capabilities CAPABILITY_NAMED_IAM \
  --no-confirm-changeset && cd ../..

# Capture Inventory ARN
INVENTORY_ARN=$(aws cloudformation describe-stacks \
  --stack-name iam-rotator-inventory \
  --query 'Stacks[0].Outputs[0].OutputValue' --output text)

# Rotation
cd sam-apps/access-key-auto-rotation && sam build && sam deploy \
  --stack-name iam-rotator-rotation \
  --parameter-overrides \
    AWSOrgID=$ORG_ID \
    DryRunFlag=$DRY_RUN \
    NotifierLambdaFunctionArn=$NOTIFIER_ARN \
  --capabilities CAPABILITY_NAMED_IAM \
  --no-confirm-changeset && cd ../..

# Capture Rotation ARN
ROTATION_ARN=$(aws cloudformation describe-stacks \
  --stack-name iam-rotator-rotation \
  --query 'Stacks[0].Outputs[0].OutputValue' --output text)
```

### 4. Deploy Orchestration Stack

```bash
aws cloudformation create-stack \
  --stack-name iam-rotator-orchestrator \
  --template-body file://templates/iam-key-auto-rotation-and-notifier-solution.yaml \
  --parameters \
    ParameterKey=AccountInventoryLambdaFunctionArn,ParameterValue=$INVENTORY_ARN \
    ParameterKey=AccessKeyRotateLambdaFunctionArn,ParameterValue=$ROTATION_ARN \
    ParameterKey=NotifierLambdaFunctionArn,ParameterValue=$NOTIFIER_ARN \
  --region $AWS_REGION

aws cloudformation wait stack-create-complete --stack-name iam-rotator-orchestrator
echo "✓ Orchestrator deployed"
```

### 5. Deploy Cross-Account Roles

```bash
# Get list of accounts
ACCOUNTS=$(aws organizations list-accounts \
  --query 'Accounts[?Status==`ACTIVE`].Id' --output text)

# Create StackSet
aws cloudformation create-stack-set \
  --stack-set-name iam-rotator-cross-account-roles \
  --template-body file://templates/iam-key-auto-rotation-iam-crossaccountrole.yaml \
  --parameters \
    ParameterKey=PrimaryAccountID,ParameterValue=$PRIMARY_ACCOUNT \
    ParameterKey=AWSOrgID,ParameterValue=$ORG_ID \
  --capabilities CAPABILITY_NAMED_IAM

# Deploy instances to all accounts
aws cloudformation create-stack-instances \
  --stack-set-name iam-rotator-cross-account-roles \
  --accounts $ACCOUNTS \
  --regions $AWS_REGION

echo "✓ Cross-account roles deploying..."
```

### 6. Create Exemption Groups (Manual per Account)

```bash
# For each member account, create exemption group
# (Can be automated but requires cross-account setup)
aws iam create-group --group-name IAMKeyRotationExemptionGroup
```

### 7. Test in Audit Mode

```bash
# Manually trigger inventory Lambda
aws lambda invoke \
  --function-name Account-Inventory-Lambda \
  --region $AWS_REGION \
  test-output.json

# Wait a minute, then check logs
aws logs tail /aws/lambda/IAM-Access-Key-Rotation-Function --follow

# Check emails received
echo "Check your inbox for rotation reports"
```

## Key Commands

### Monitor Execution

```bash
# Watch rotation in progress
aws logs tail /aws/lambda/IAM-Access-Key-Rotation-Function --follow

# View last 50 rotations
aws logs filter-log-events \
  --log-group-name /aws/lambda/IAM-Access-Key-Rotation-Function \
  --filter-pattern "ACTION: ROTATE" \
  --max-items 50
```

### Force Rotation (Emergency)

```bash
# Rotate specific user immediately
aws lambda invoke \
  --function-name IAM-Access-Key-Rotation-Function \
  --payload '{
    "account": "123456789012",
    "name": "account-name",
    "email": "owner@company.com",
    "dryrun": false,
    "force_rotate_users": ["compromised.user"],
    "tags": {}
  }' \
  --region us-east-1 \
  output.json
```

### Exempt User

```bash
# Skip rotation for service account
aws iam add-user-to-group \
  --group-name IAMKeyRotationExemptionGroup \
  --user-name service-account

# Later, re-enable rotation
aws iam remove-user-from-group \
  --group-name IAMKeyRotationExemptionGroup \
  --user-name service-account
```

### Enable Enforcement Mode

After validating in audit mode:

```bash
# Switch to enforcement (actual key rotation)
aws lambda update-function-configuration \
  --function-name IAM-Access-Key-Rotation-Function \
  --environment Variables="{DryRunFlag=False}" \
  --region us-east-1

echo "⚠️  Enforcement mode enabled - rotations will execute!"
```

## Configuration Quick Reference

| Setting | Default | Location | Purpose |
|---------|---------|----------|---------|
| `RotationPeriod` | 90 days | SAM Parameter | Days before rotation |
| `DryRunFlag` | True | Lambda Env Var | Audit vs. Enforce mode |
| `IAMExemptionGroup` | IAMKeyRotationExemptionGroup | Lambda Env Var | Group for exempted users |
| `Schedule` | cron(0 5 ? * 1 *) | CloudWatch Rule | Monday 5 AM UTC |
| `Timeout` | 400 sec | Lambda Config | Max execution time |

**Change rotation period**:

```bash
aws cloudformation update-stack \
  --stack-name iam-rotator-rotation \
  --parameters ParameterKey=RotationPeriod,ParameterValue=180
```

## Troubleshooting Quick Fixes

### "No emails received"

```bash
# 1. Check SES verified addresses
aws ses list-verified-email-addresses

# 2. Verify recipient (in sandbox)
aws ses verify-email-identity --email-address recipient@company.com

# 3. Check notifier logs
aws logs tail /aws/lambda/Notifier-Lambda
```

### "Cross-account role not found"

```bash
# 1. Check StackSet deployment status
aws cloudformation list-stack-instances \
  --stack-set-name iam-rotator-cross-account-roles

# 2. Check role exists in member account
aws iam get-role \
  --role-name iam-key-rotation-lambda-assumed-role
```

### "Lambda timeout"

```bash
# Increase timeout from 400 to 600 seconds
aws lambda update-function-configuration \
  --function-name IAM-Access-Key-Rotation-Function \
  --timeout 600
```

### "Keys not rotating (DryRunFlag=False)"

```bash
# Check actual environment variable
aws lambda get-function-configuration \
  --function-name IAM-Access-Key-Rotation-Function \
  --query 'Environment.Variables.DryRunFlag'

# Check account tags (may override global flag)
aws organizations list-tags-for-resource --resource-id 123456789012
```

## Architecture Diagram

```
┌─────────────────────────────────────────────┐
│         AWS Organization                     │
│  ┌──────────────────────────────────────┐   │
│  │  Primary Account (Rotator)           │   │
│  │  ┌──────────────────────────────┐    │   │
│  │  │ CloudWatch Event (5 AM UTC)  │    │   │
│  │  │         every Monday         │    │   │
│  │  └────────────┬─────────────────┘    │   │
│  │               │                       │   │
│  │  ┌────────────▼─────────────────┐    │   │
│  │  │ Inventory Lambda             │    │   │
│  │  │ - List accounts              │    │   │
│  │  │ - Get tags                   │    │   │
│  │  └────────────┬─────────────────┘    │   │
│  │               │                       │   │
│  │  ┌────────────▼─────────────────┐    │   │
│  │  │ Rotation Lambda (parallel)   │    │   │
│  │  │ - Assume cross-account role  │    │   │
│  │  │ - Scan keys                  │    │   │
│  │  │ - Rotate/delete              │    │   │
│  │  └────────────┬─────────────────┘    │   │
│  │               │                       │   │
│  │  ┌────────────▼─────────────────┐    │   │
│  │  │ Notifier Lambda              │    │   │
│  │  │ - Send emails                │    │   │
│  │  │ - Log results                │    │   │
│  │  └──────────────────────────────┘    │   │
│  └──────────────────────────────────────┘   │
│                   │                         │
│                   ▼ (AssumeRole)            │
│  ┌──────────────────────────────────────┐   │
│  │  All Member Accounts                 │   │
│  │  ┌──────────────────────────────┐    │   │
│  │  │ Assumed Role                 │    │   │
│  │  │ - Manage IAM keys            │    │   │
│  │  │ - Access Secrets Manager     │    │   │
│  │  └──────────────────────────────┘    │   │
│  └──────────────────────────────────────┘   │
└─────────────────────────────────────────────┘
```

## Cost Estimate

For typical organization (500 accounts):

| Component | Cost |
|-----------|------|
| Lambda Invocations (1500/month) | $0.20 |
| Lambda Compute (1000 GB-seconds/month) | $2.00 |
| CloudWatch Events | $0.10 |
| SES (500 emails/month) | $50 |
| Secrets Manager (500 secrets) | $2.50 |
| **Total** | **~$55/month** |

## Next Steps

1. **Deploy**: Follow Quick Deploy section above
2. **Test**: Verify in audit mode for 1-2 cycles
3. **Configure**: Adjust rotation period if needed
4. **Communicate**: Notify teams before enforcement
5. **Enable**: Switch to enforcement mode
6. **Monitor**: Set up CloudWatch alarms
7. **Maintain**: Use operational scripts from OPERATIONS.md

## Documentation Map

| Document | Purpose | Audience |
|----------|---------|----------|
| [README.md](../README.md) | Complete reference | Everyone |
| [ARCHITECTURE.md](./ARCHITECTURE.md) | Technical design | Architects, DevOps |
| [DESIGN.md](./DESIGN.md) | Features & decisions | Engineers |
| [IMPLEMENTATION.md](./IMPLEMENTATION.md) | Step-by-step deploy | DevOps, Platform Teams |
| [OPERATIONS.md](./OPERATIONS.md) | Daily operations | Operations, On-Call |
| [QUICK_START.md](./QUICK_START.md) | Fast setup (this file) | Everyone |

## Support & Help

**Issue?**
1. Check troubleshooting section above
2. Review operation logs: `aws logs tail /aws/lambda/...`
3. See detailed troubleshooting in README.md

**Questions?**
- Architecture: See ARCHITECTURE.md
- Features: See DESIGN.md  
- Operations: See OPERATIONS.md
- Implementation: See IMPLEMENTATION.md

---

**Version**: 2.0  
**Updated**: 2026-08-04  
**Status**: Production Ready
