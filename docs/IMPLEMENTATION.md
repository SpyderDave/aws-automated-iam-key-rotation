# Implementation Guide

## Overview

This guide provides step-by-step instructions for implementing the IAM Key Auto-Rotation solution in your AWS Organization using GitHub Actions, Sceptre, and AWS SAM.

## Pre-Implementation Checklist

### Prerequisites

- [ ] AWS CLI v2 installed and configured
- [ ] AWS SAM CLI v1.0+ installed
- [ ] Python 3.9+ installed
- [ ] AWS Organizations enabled and configured
- [ ] Primary account identified (for rotator deployment)
- [ ] AWS Organization ID available
- [ ] List of target Organizational Units (OUs)
- [ ] Email address for notifications (SES verified)
- [ ] S3 buckets for SAM artifact storage (one per environment: NONPROD & PROD)
- [ ] IAM permissions to create CloudFormation stacks and StackSets
- [ ] GitHub repository access with ability to add secrets/variables

### AWS Permissions Required

The deploying user/role must have:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "cloudformation:*",
        "iam:*",
        "lambda:*",
        "events:*",
        "ses:*",
        "organizations:*",
        "secretsmanager:*",
        "s3:*",
        "logs:*"
      ],
      "Resource": "*"
    }
  ]
}
```

## Step 1: AWS Organizations Setup

### 1.1 Enable AWS Organizations (if not already enabled)

```bash
aws organizations describe-organization

# If not enabled:
aws organizations create-organization --feature-set ALL
```

### 1.2 Collect Organization Information

```bash
# Get Organization ID
ORG_ID=$(aws organizations describe-organization \
  --query 'Organization.Id' \
  --output text)
echo "Organization ID: $ORG_ID"

# Get Primary Account ID
PRIMARY_ACCOUNT=$(aws sts get-caller-identity \
  --query 'Account' \
  --output text)
echo "Primary Account: $PRIMARY_ACCOUNT"

# List all OUs
aws organizations list-roots --query 'Roots[0].Id' --output text
aws organizations list-children \
  --parent-id <root-id> \
  --child-type ORGANIZATIONAL_UNIT
```

### 1.3 Enable Trusted Access for CloudFormation StackSets

```bash
aws organizations enable-trusted-access \
  --service-principal cloudformation.amazonaws.com
```

## Step 2: SES Configuration

### 2.1 Verify Sender Email Address

```bash
# Verify email address
aws ses verify-email-identity \
  --email-address ops@company.com \
  --region us-east-1

# Confirm from inbox, then check verification status
aws ses list-verified-email-addresses --region us-east-1
```

### 2.2 Verify Recipient Emails (in sandbox mode)

```bash
# If in SES Sandbox, verify all recipient addresses
aws ses verify-email-identity \
  --email-address recipient@company.com \
  --region us-east-1
```

### 2.3 Exit SES Sandbox (for production)

Submit AWS Support case to enable production SES access.

## Step 3: Create S3 Buckets for SAM Artifacts

Email templates are now **embedded directly in Lambda code** (no S3 dependency). However, SAM packaging requires S3 buckets to store Lambda artifact code during deployment.

### 3.1 Create S3 Buckets for Each Environment

```bash
# Create NONPROD environment artifact bucket
NONPROD_ARTIFACT_BUCKET="sam-artifacts-nonprod-$(date +%s)"

aws s3 mb s3://$NONPROD_ARTIFACT_BUCKET --region us-east-1

# Create PROD environment artifact bucket
PROD_ARTIFACT_BUCKET="sam-artifacts-prod-$(date +%s)"

aws s3 mb s3://$PROD_ARTIFACT_BUCKET --region us-east-1

# Enable versioning on both buckets
aws s3api put-bucket-versioning \
  --bucket $NONPROD_ARTIFACT_BUCKET \
  --versioning-configuration Status=Enabled

aws s3api put-bucket-versioning \
  --bucket $PROD_ARTIFACT_BUCKET \
  --versioning-configuration Status=Enabled
```

### 3.2 Enable Bucket Encryption (Optional but Recommended)

```bash
# For NONPROD bucket
aws s3api put-bucket-encryption \
  --bucket $NONPROD_ARTIFACT_BUCKET \
  --server-side-encryption-configuration '{
    "Rules": [{
      "ApplyServerSideEncryptionByDefault": {
        "SSEAlgorithm": "AES256"
      }
    }]
  }'

# For PROD bucket
aws s3api put-bucket-encryption \
  --bucket $PROD_ARTIFACT_BUCKET \
  --server-side-encryption-configuration '{
    "Rules": [{
      "ApplyServerSideEncryptionByDefault": {
        "SSEAlgorithm": "AES256"
      }
    }]
  }'
```

### 3.3 Document Artifact Bucket Names

Save these for GitHub Actions configuration:
```bash
echo "NONPROD Artifact Bucket: $NONPROD_ARTIFACT_BUCKET"
echo "PROD Artifact Bucket: $PROD_ARTIFACT_BUCKET"
```

**Note**: These buckets are used **only** during deployment for SAM packaging. Lambda code is uploaded here temporarily and referenced in CloudFormation templates. Email templates are **embedded in the Lambda code** itself.

## Step 4: GitHub Actions Setup

### 4.1 Add GitHub Actions Secrets

In your GitHub repository, go to **Settings → Secrets and variables → Actions** and add:

**NONPROD Environment**:
- `ORG_ID_NONPROD` - AWS Organization ID for NONPROD
- `DRY_RUN_NONPROD` - Set to `"True"` for audit mode (recommended initially)
- `ADMIN_EMAIL` - Email for notifications (shared across environments)
- `SAM_ARTIFACT_BUCKET_NONPROD` - S3 bucket name for SAM artifacts
- `PROD_ORG_ID` - (Optional) For validation checks

**PROD Environment**:
- `ORG_ID_PROD` - AWS Organization ID for PROD
- `DRY_RUN_PROD` - Set to `"False"` for enforcement (after validation)
- `SAM_ARTIFACT_BUCKET_PROD` - S3 bucket name for SAM artifacts

### 4.2 Add GitHub Actions Variables

Go to **Settings → Secrets and variables → Actions → Variables** and add:

**NONPROD Environment**:
- `AWS_ROLE_TO_ASSUME_NONPROD` - OIDC role ARN (see SETUP_TWO_ORGS.md)
- `PRIMARY_ACCOUNT_ID_NONPROD` - AWS Account ID

**PROD Environment**:
- `AWS_ROLE_TO_ASSUME_PROD` - OIDC role ARN (see SETUP_TWO_ORGS.md)
- `PRIMARY_ACCOUNT_ID_PROD` - AWS Account ID

See [.github/SETUP_TWO_ORGS.md](.github/SETUP_TWO_ORGS.md) for complete OIDC and IAM role setup.

## Step 5: Understanding the SAM Build & Package Workflow

### 5.1 How SAM Build & Package Works

The GitHub Actions workflows follow this process:

```
1. sam build
   ├─ Compiles SAM template into CloudFormation
   └─ Creates .aws-sam/build/ with Lambda code

2. sam package
   ├─ Zips Lambda code
   ├─ Uploads to S3 artifact bucket
   └─ Generates packaged CloudFormation template with S3 URIs

3. Sceptre deploy
   ├─ Reads packaged CloudFormation template
   ├─ Deploys via CloudFormation
   └─ References S3 Lambda artifacts from step 2
```

### 5.2 Why This Matters

- **Build isolation**: Each environment gets separate artifact buckets
- **Proper packaging**: SAM handles Lambda code zipping and S3 upload automatically
- **Clean deployments**: Sceptre deploys pre-packaged templates with correct code references
- **Artifact cleanup**: Old artifacts remain in S3 for rollback; configure lifecycle policies if needed

## Step 6: Deployment via GitHub Actions

### 6.1 Trigger NONPROD Deployment (Audit Mode)

1. Go to **Actions → Deploy to NONPROD**
2. Click **Run workflow**
3. Select stack: `all` (deploys notifier, inventory, rotation, cross-account)
4. Confirm execution

Monitor logs for:
- Successful SAM build & package steps
- Sceptre stack deployments
- Email notifications in audit mode

### 6.2 Trigger PROD Deployment (Enforcement Mode)

1. Go to **Actions → Deploy to PROD**
2. Click **Run workflow**
3. Select stack: `all`
4. **Approve deployment** when prompted (requires GitHub environment approval)
5. Confirm execution

Note: PROD deployments require explicit approval before execution.

### 6.3 Selective Deployments

Deploy individual stacks without redeploying everything:

```
Stack options:
- all: Deploy notifier, inventory, rotation, and cross-account roles
- notifier: Deploy only the Notifier Lambda
- inventory: Deploy only the Account Inventory Lambda
- rotation: Deploy only the Access Key Rotation Lambda
- cross-account: Deploy only the cross-account IAM roles via StackSet
```

## Step 7: Verify Deployment

### 7.1 Check CloudFormation Stacks

```bash
aws cloudformation list-stacks \
  --region us-east-1 \
  --stack-status-filter CREATE_COMPLETE UPDATE_COMPLETE \
  --query 'StackSummaries[?contains(StackName, `iam-rotator-`) || contains(StackName, `iam-key-rotator`)].{Name:StackName,Status:StackStatus}' \
  --output table
```

### 7.2 Verify Lambda Functions

```bash
aws lambda list-functions \
  --region us-east-1 \
  --query 'Functions[?contains(FunctionName, `IAM-`) || contains(FunctionName, `Rotation`)].{Name:FunctionName,Runtime:Runtime,CodeSize:CodeSize}' \
  --output table
```

### 7.3 Test Audit Mode

```bash
# Manually invoke the Account Inventory Lambda
aws lambda invoke \
  --function-name Account-Inventory \
  --region us-east-1 \
  test-output.json

# View output
cat test-output.json
```

### 7.4 Monitor CloudWatch Logs

```bash
# Follow inventory logs
aws logs tail /aws/lambda/Account-Inventory --follow

# Follow rotation logs  
aws logs tail /aws/lambda/IAM-Access-Key-Rotation-Function --follow

# Follow notifier logs
aws logs tail /aws/lambda/Notifier --follow
```

## Step 8: Email Template Customization

Email templates are **embedded in the Notifier Lambda code** for reliability and simplicity.

### 8.1 Locate Templates

Templates are defined in: `sam-apps/notifier/notifier.py`

The `EMAIL_TEMPLATES` dictionary contains:
- `iam-auto-key-rotation-audit.html` - Audit mode email template
- `iam-auto-key-rotation-enforcement.html` - Enforcement mode email template

### 8.2 Customize Templates

Edit `sam-apps/notifier/notifier.py`:

```python
EMAIL_TEMPLATES = {
    'iam-auto-key-rotation-audit.html': '''
        <h1>Custom Audit Email</h1>
        <p>Your custom HTML here...</p>
    ''',
    'iam-auto-key-rotation-enforcement.html': '''
        <h1>Custom Enforcement Email</h1>
        <p>Your custom HTML here...</p>
    '''
}
```

### 8.3 Deploy Updated Templates

After modifying templates:

1. Commit changes to repository
2. Trigger **Deploy to NONPROD** workflow
3. Select `notifier` stack only
4. Verify in logs that new template is embedded
5. Send test notification to verify rendering


## Step 9: Transition to Enforcement Mode

### 9.1 Validate in Audit Mode First

Run in NONPROD environment with `DRY_RUN_NONPROD=True`:

1. Verify account inventory is complete
2. Check rotation analysis is correct
3. Review email template rendering
4. Validate no errors in CloudWatch Logs
5. Confirm SES email delivery works

### 9.2 Update DRY_RUN_PROD Secret

Once validated:

1. Go to GitHub **Settings → Secrets → Actions**
2. Edit `DRY_RUN_PROD`
3. Change value from `"True"` to `"False"`
4. Save

### 9.3 Enable Gradual Enforcement via Account Tags

You can control which accounts are rotated using AWS tags:

```bash
# Tag production accounts for strict enforcement
aws organizations tag-resource \
  --resource-id 123456789012 \
  --tags Key=iamRotationPolicy,Value=Strict

# Others remain in standard mode (audit only)
```

See [docs/ACCOUNT_TAGGING.md](ACCOUNT_TAGGING.md) for detailed tagging strategy.

## Step 10: Operational Tasks

### 10.1 Document Configuration

```bash
cat > deployment-config.sh <<EOF
#!/bin/bash
# Deployment Configuration - $(date)

export PRIMARY_ACCOUNT_NONPROD="123456789012"
export PRIMARY_ACCOUNT_PROD="210987654321"
export AWS_REGION="us-east-1"
export ORG_ID_NONPROD="o-xxxxxxxxxx"
export ORG_ID_PROD="o-yyyyyyyyyy"
export ADMIN_EMAIL="ops@company.com"

export NONPROD_ARTIFACT_BUCKET="$NONPROD_ARTIFACT_BUCKET"
export PROD_ARTIFACT_BUCKET="$PROD_ARTIFACT_BUCKET"

# Lambda Functions
export NOTIFIER_FN="Notifier"
export INVENTORY_FN="Account-Inventory"
export ROTATION_FN="IAM-Access-Key-Rotation-Function"
EOF

chmod +x deployment-config.sh
```

### 10.2 Set Up CloudWatch Alarms

```bash
# Create alarm for rotation failures
aws cloudwatch put-metric-alarm \
  --alarm-name iam-rotation-errors \
  --alarm-description "Alert on IAM rotation Lambda errors" \
  --metric-name Errors \
  --namespace AWS/Lambda \
  --statistic Sum \
  --period 3600 \
  --threshold 5 \
  --comparison-operator GreaterThanThreshold \
  --dimensions Name=FunctionName,Value=IAM-Access-Key-Rotation-Function \
  --alarm-actions arn:aws:sns:us-east-1:$PRIMARY_ACCOUNT:ops-alerts
```

### 10.3 Create CloudWatch Dashboard

```bash
# Monitor rotation health
aws cloudwatch put-dashboard \
  --dashboard-name IAM-Key-Rotation \
  --dashboard-body file://dashboards/rotation-dashboard.json
```

### 10.4 Enable CloudTrail Logging

```bash
# Log all IAM changes
aws cloudtrail create-trail \
  --name iam-rotation-audit \
  --s3-bucket-name company-cloudtrail-logs \
  --is-multi-region-trail

aws cloudtrail start-logging --trail-name iam-rotation-audit
```

## Step 11: Troubleshooting

### Issue: SAM Package Fails - "S3 bucket does not exist"

**Solution**: Verify artifact bucket name in GitHub Actions secret matches actual bucket:
```bash
aws s3 ls | grep sam-artifacts
```

### Issue: Lambda Code Not Updated After Deploy

**Solution**: Ensure `sam build` ran successfully and produced `.aws-sam/build/` directory:
```bash
ls -la sam-apps/notifier/.aws-sam/build/
```

### Issue: Sceptre Deploy Fails - "Template URL invalid"

**Solution**: Verify packaged template exists in expected location:
```bash
ls -la packaged-templates/notifier.yaml
```

### Issue: Emails Not Received

**Solution**: Check:
1. SES is out of sandbox: `aws ses describe-configuration-set --configuration-set-name default`
2. Sender email is verified: `aws ses list-verified-email-addresses`
3. Recipient email is verified (if in sandbox)
4. CloudWatch Logs for Notifier Lambda errors
5. CloudWatch Logs for SES delivery status

## Rollback Procedures

### If Issues Discovered

#### 1. Disable Rotation Immediately

```bash
# Disable CloudWatch event rule
aws events disable-rule \
  --name RotationCloudWatchEventLambdaTrigger \
  --region us-east-1
```

#### 2. Revert to Audit Mode

```bash
aws lambda update-function-configuration \
  --function-name IAM-Access-Key-Rotation-Function \
  --environment Variables="{DryRunFlag=True}" \
  --region us-east-1
```

#### 3. Investigate Issues

- Review CloudWatch Logs
- Check IAM permissions
- Validate cross-account role setup
- Test with single account

#### 4. Recovery

```bash
# Re-enable when resolved
aws events enable-rule \
  --name RotationCloudWatchEventLambdaTrigger \
  --region us-east-1
```

---

**Document Version**: 2.1  
**Last Updated**: 2026-08-04  
**Status**: Updated for SAM Build & Package Workflow
