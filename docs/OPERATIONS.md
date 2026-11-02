# Operations & Maintenance Guide

## Daily Operations

### Monitoring Dashboard

Create a CloudWatch Dashboard for visibility:

```bash
aws cloudwatch put-dashboard \
  --dashboard-name IAMKeyRotation \
  --dashboard-body file://dashboard.json
```

**Dashboard JSON** (`dashboard.json`):

```json
{
  "widgets": [
    {
      "type": "metric",
      "properties": {
        "metrics": [
          ["AWS/Lambda", "Invocations", {"stat": "Sum"}],
          [".", "Errors", {"stat": "Sum"}],
          [".", "Duration", {"stat": "Average"}],
          [".", "Throttles", {"stat": "Sum"}]
        ],
        "period": 3600,
        "stat": "Average",
        "region": "us-east-1",
        "title": "Lambda Health"
      }
    },
    {
      "type": "log",
      "properties": {
        "query": "fields @timestamp, @message | stats count() by @message",
        "region": "us-east-1",
        "title": "Recent Rotations"
      }
    }
  ]
}
```

### Health Checks

**Daily**:

```bash
#!/bin/bash
# health-check.sh

REGION="us-east-1"
THRESHOLD_HOURS=25

# Check last Inventory Lambda execution
LAST_EXEC=$(aws logs describe-log-streams \
  --log-group-name /aws/lambda/Account-Inventory-Lambda \
  --order-by LastEventTime \
  --descending \
  --region $REGION \
  --query 'logStreams[0].lastEventTimestamp' \
  --output text)

HOURS_AGO=$(( ($(date +%s%N) - LAST_EXEC) / 3600000000000 ))

if [ "$HOURS_AGO" -gt "$THRESHOLD_HOURS" ]; then
  echo "⚠️  WARNING: Inventory Lambda hasn't run in $HOURS_AGO hours"
else
  echo "✓ Inventory Lambda healthy (last run: $HOURS_AGO hours ago)"
fi

# Check for errors
ERRORS=$(aws logs filter-log-events \
  --log-group-name /aws/lambda/IAM-Access-Key-Rotation-Function \
  --filter-pattern "ERROR" \
  --start-time $(($(date +%s) - 86400)) \
  --region $REGION \
  --query 'events | length(@)' \
  --output text)

if [ "$ERRORS" -gt 0 ]; then
  echo "⚠️  WARNING: Found $ERRORS errors in rotation Lambda"
else
  echo "✓ No errors in rotation Lambda"
fi
```

Run daily via cron:

```bash
0 6 * * * cd /opt/monitoring && ./health-check.sh | mail -s "IAM Rotation Health" ops@company.com
```

## Operational Tasks

### Add User to Exemption Group

When service accounts or special users need to be exempted:

```bash
#!/bin/bash
# exempt-user.sh

ACCOUNT_ID=$1
USERNAME=$2

if [ -z "$ACCOUNT_ID" ] || [ -z "$USERNAME" ]; then
  echo "Usage: $0 <account-id> <username>"
  exit 1
fi

# Assume cross-account role
CREDS=$(aws sts assume-role \
  --role-arn "arn:aws:iam::$ACCOUNT_ID:role/iam-key-rotation-lambda-assumed-role" \
  --role-session-name "exemption-mgmt" \
  --query 'Credentials.[AccessKeyId,SecretAccessKey,SessionToken]' \
  --output text)

read AWS_ACCESS_KEY_ID AWS_SECRET_ACCESS_KEY AWS_SESSION_TOKEN <<< "$CREDS"

# Add user to exemption group
AWS_ACCESS_KEY_ID=$AWS_ACCESS_KEY_ID \
AWS_SECRET_ACCESS_KEY=$AWS_SECRET_ACCESS_KEY \
AWS_SESSION_TOKEN=$AWS_SESSION_TOKEN \
aws iam add-user-to-group \
  --group-name IAMKeyRotationExemptionGroup \
  --user-name $USERNAME

echo "✓ User $USERNAME exempted from rotation in account $ACCOUNT_ID"
```

**Usage**:

```bash
./exempt-user.sh 123456789012 service-account
```

### Remove User from Exemption Group

When exemption expires:

```bash
#!/bin/bash
# unempt-user.sh

ACCOUNT_ID=$1
USERNAME=$2

CREDS=$(aws sts assume-role \
  --role-arn "arn:aws:iam::$ACCOUNT_ID:role/iam-key-rotation-lambda-assumed-role" \
  --role-session-name "exemption-mgmt" \
  --query 'Credentials.[AccessKeyId,SecretAccessKey,SessionToken]' \
  --output text)

read AWS_ACCESS_KEY_ID AWS_SECRET_ACCESS_KEY AWS_SESSION_TOKEN <<< "$CREDS"

AWS_ACCESS_KEY_ID=$AWS_ACCESS_KEY_ID \
AWS_SECRET_ACCESS_KEY=$AWS_SECRET_ACCESS_KEY \
AWS_SESSION_TOKEN=$AWS_SESSION_TOKEN \
aws iam remove-user-from-group \
  --group-name IAMKeyRotationExemptionGroup \
  --user-name $USERNAME

echo "✓ User $USERNAME re-enabled for rotation in account $ACCOUNT_ID"
```

### Force Immediate Rotation

For emergency key rotation:

```bash
#!/bin/bash
# force-rotate.sh

ACCOUNT_ID=$1
USERNAME=$2

if [ -z "$ACCOUNT_ID" ] || [ -z "$USERNAME" ]; then
  echo "Usage: $0 <account-id> <username>"
  exit 1
fi

# Get account details from Organizations
ACCOUNT_NAME=$(aws organizations describe-account \
  --account-id $ACCOUNT_ID \
  --query 'Account.Name' \
  --output text)

ACCOUNT_EMAIL=$(aws organizations describe-account \
  --account-id $ACCOUNT_ID \
  --query 'Account.Email' \
  --output text)

# Create Lambda payload
cat > payload.json <<EOF
{
  "account": "$ACCOUNT_ID",
  "name": "$ACCOUNT_NAME",
  "email": "$ACCOUNT_EMAIL",
  "dryrun": false,
  "force_rotate_users": ["$USERNAME"],
  "tags": {}
}
EOF

# Invoke rotation Lambda
aws lambda invoke \
  --function-name IAM-Access-Key-Rotation-Function \
  --payload file://payload.json \
  --region us-east-1 \
  output.json

# Show result
cat output.json

rm payload.json output.json
```

**Usage**:

```bash
./force-rotate.sh 123456789012 compromised-user
```

### View Key Rotation History

Query logs for specific user or account:

```bash
#!/bin/bash
# rotation-history.sh

SEARCH_TERM=$1

if [ -z "$SEARCH_TERM" ]; then
  echo "Usage: $0 <username|account-id>"
  exit 1
fi

aws logs filter-log-events \
  --log-group-name /aws/lambda/IAM-Access-Key-Rotation-Function \
  --filter-pattern "$SEARCH_TERM" \
  --start-time $(($(date +%s) - 86400 * 30)) \
  --region us-east-1 \
  --query 'events[*].[@timestamp,@message]' \
  --output table
```

### Generate Compliance Report

Monthly compliance audit:

```bash
#!/bin/bash
# compliance-report.sh

REPORT_DATE=$(date +%Y-%m-%d)
REPORT_FILE="rotation-report-$REPORT_DATE.txt"

cat > "$REPORT_FILE" <<EOF
IAM Key Rotation Compliance Report
Generated: $REPORT_DATE

=== EXECUTION SUMMARY ===
EOF

# Count successful rotations
aws logs filter-log-events \
  --log-group-name /aws/lambda/IAM-Access-Key-Rotation-Function \
  --filter-pattern "ROTATE" \
  --start-time $(($(date +%s) - 86400 * 30)) \
  --region us-east-1 \
  --query 'events | length(@)' \
  --output text >> "$REPORT_FILE"

# Count errors
echo -e "\n=== ERROR SUMMARY ===" >> "$REPORT_FILE"
aws logs filter-log-events \
  --log-group-name /aws/lambda/IAM-Access-Key-Rotation-Function \
  --filter-pattern "ERROR" \
  --start-time $(($(date +%s) - 86400 * 30)) \
  --region us-east-1 \
  --query 'events[*].@message' \
  --output text >> "$REPORT_FILE"

# Count exempted users
echo -e "\n=== EXEMPTED USERS ===" >> "$REPORT_FILE"
for ACCOUNT_ID in $(aws organizations list-accounts --query 'Accounts[?Status==`ACTIVE`].Id' --output text); do
  CREDS=$(aws sts assume-role \
    --role-arn "arn:aws:iam::$ACCOUNT_ID:role/iam-key-rotation-lambda-assumed-role" \
    --role-session-name "report-gen" \
    --query 'Credentials.[AccessKeyId,SecretAccessKey,SessionToken]' \
    --output text 2>/dev/null)
  
  if [ -n "$CREDS" ]; then
    read AWS_ACCESS_KEY_ID AWS_SECRET_ACCESS_KEY AWS_SESSION_TOKEN <<< "$CREDS"
    
    MEMBERS=$(AWS_ACCESS_KEY_ID=$AWS_ACCESS_KEY_ID \
    AWS_SECRET_ACCESS_KEY=$AWS_SECRET_ACCESS_KEY \
    AWS_SESSION_TOKEN=$AWS_SESSION_TOKEN \
    aws iam get-group \
      --group-name IAMKeyRotationExemptionGroup \
      --query 'Users[*].UserName' \
      --output text 2>/dev/null)
    
    if [ -n "$MEMBERS" ]; then
      echo "$ACCOUNT_ID: $MEMBERS" >> "$REPORT_FILE"
    fi
  fi
done

echo -e "\n✓ Report generated: $REPORT_FILE"
```

## Troubleshooting Guide

### Issue: Lambda Timeout

**Symptoms**: Lambda execution exceeds timeout, partial processing

**Solution**:

```bash
# Increase timeout from 400 to 600 seconds
aws lambda update-function-configuration \
  --function-name IAM-Access-Key-Rotation-Function \
  --timeout 600 \
  --region us-east-1

# For very large orgs (1000+ accounts), consider OU-based targeting
aws lambda update-function-configuration \
  --function-name Account-Inventory-Lambda \
  --environment Variables="{LambdaRotationFunction=...,InventoryOU=ou-xxxx-aaaaaaaa}" \
  --region us-east-1
```

### Issue: Cross-Account Role Assumption Fails

**Symptoms**: "AccessDenied" when assuming role in member accounts

**Debug**:

```bash
# Test role assumption
aws sts assume-role \
  --role-arn "arn:aws:iam::MEMBER_ACCOUNT:role/iam-key-rotation-lambda-assumed-role" \
  --role-session-name test \
  --region us-east-1

# Check if role exists
aws iam get-role \
  --role-name iam-key-rotation-lambda-assumed-role \
  --region us-east-1

# Check trust relationship
aws iam get-role \
  --role-name iam-key-rotation-lambda-assumed-role \
  --query 'Role.AssumeRolePolicyDocument'
```

**Solutions**:

1. Verify StackSet deployed successfully to member account
2. Check role name matches configuration
3. Validate trust includes primary account ID
4. Ensure organization ID condition is correct

### Issue: Email Not Sending

**Symptoms**: Rotation executes but no email received

**Debug**:

```bash
# Check SES verified addresses
aws ses list-verified-email-addresses \
  --region us-east-1

# Check SES sending quota
aws ses get-send-statistics --region us-east-1

# Check notifier Lambda logs
aws logs tail /aws/lambda/Notifier-Lambda \
  --follow \
  --region us-east-1

# Test SES manually
aws ses send-email \
  --from ops@company.com \
  --to test@company.com \
  --subject "Test" \
  --text "Test email" \
  --region us-east-1
```

**Solutions**:

1. Verify sender email is SES-verified
2. Verify recipient email in SES sandbox
3. Request production access from AWS Support
4. Check S3 bucket permissions for templates
5. Verify email template format (must be valid HTML)

### Issue: Keys Not Rotating (Mode=Enforce)

**Symptoms**: DryRunFlag=False but no keys created/deleted

**Debug**:

```bash
# Check Lambda environment variables
aws lambda get-function-configuration \
  --function-name IAM-Access-Key-Rotation-Function \
  --query 'Environment.Variables' \
  --region us-east-1

# Review rotation logs with EXECUTE filter
aws logs filter-log-events \
  --log-group-name /aws/lambda/IAM-Access-Key-Rotation-Function \
  --filter-pattern "EXECUTE\|execute\|created\|deactivated" \
  --region us-east-1

# Check cross-account role permissions
aws iam get-role-policy \
  --role-name iam-key-rotation-lambda-assumed-role \
  --policy-name AllowRotationFunctionPermissions \
  --region us-east-1
```

**Common Causes**:

1. Account tagged with `iamRotationPolicy=Standard` (forces audit)
2. All users in exemption group
3. No keys older than rotation period
4. IAM permissions missing in cross-account role
5. DryRunFlag actually set to "True" (check case sensitivity)

### Issue: Secrets Manager Creation Fails

**Symptoms**: Error "AccessDenied on CreateSecret"

**Debug**:

```bash
# Check SecretsManager policy on assumed role
aws iam get-role-policy \
  --role-name iam-key-rotation-lambda-assumed-role \
  --policy-name AllowRotationFunctionPermissions \
  --region us-east-1 | jq '.RolePolicyDocument.Statement[] | select(.Action | contains("secretsmanager"))'

# Test secret creation
aws secretsmanager create-secret \
  --name test-secret \
  --secret-string '{"key":"value"}' \
  --region us-east-1

# Verify KMS encryption (if using custom KMS key)
aws kms describe-key --key-id arn:aws:kms:... --region us-east-1
```

**Solutions**:

1. Ensure SecretsManager permissions added to cross-account role
2. Grant KMS permissions if using custom encryption key
3. Verify resource policies on secret/KMS key

## Performance Tuning

### Large Organization (500+ accounts)

**Configuration**:

```bash
# Set higher timeout
aws lambda update-function-configuration \
  --function-name IAM-Access-Key-Rotation-Function \
  --timeout 900 \
  --region us-east-1

# Use OU targeting instead of all accounts
aws lambda update-function-configuration \
  --function-name Account-Inventory-Lambda \
  --environment Variables="{LambdaRotationFunction=...,InventoryOU=ou-xxxx-yyyyyyy}" \
  --region us-east-1

# Consider batch processing over multiple days
# Schedule multiple Inventory invocations for different OUs
aws events put-rule \
  --name RotationCloudWatchEventProd \
  --schedule-expression 'cron(0 5 ? * 1 *)'  # Monday

aws events put-rule \
  --name RotationCloudWatchEventNonProd \
  --schedule-expression 'cron(0 5 ? * 3 *)'  # Wednesday
```

### Concurrent Execution Limits

```bash
# Set reserved concurrency to max expected account count
aws lambda put-function-concurrency \
  --function-name IAM-Access-Key-Rotation-Function \
  --reserved-concurrent-executions 1000 \
  --region us-east-1

# Monitor concurrency
aws cloudwatch get-metric-statistics \
  --namespace AWS/Lambda \
  --metric-name ConcurrentExecutions \
  --dimensions Name=FunctionName,Value=IAM-Access-Key-Rotation-Function \
  --start-time 2026-08-03T00:00:00Z \
  --end-time 2026-08-04T00:00:00Z \
  --period 3600 \
  --statistics Maximum
```

## Updating Configuration

### Change Rotation Period

```bash
# Update through CloudFormation
aws cloudformation update-stack \
  --stack-name iam-rotator-rotation \
  --use-previous-template \
  --parameters ParameterKey=RotationPeriod,ParameterValue=120 \
  --region us-east-1
```

### Update Email Templates

```bash
# Update template in S3
aws s3 cp email-template.html \
  s3://company-templates/email-templates/iam-auto-key-rotation-enforcement.html \
  --region us-east-1

# Lambda reads template on next invocation (no restart needed)
```

### Enable/Disable Notifications

```bash
# Disable notifier by removing Lambda invocation
# (manual code change or conditional invocation)

# Or disable SES sending in notifier Lambda
aws lambda update-function-configuration \
  --function-name Notifier-Lambda \
  --environment Variables="{SEND_EMAIL=false}" \
  --region us-east-1
```

## Backup & Recovery

### Backup Configuration

```bash
#!/bin/bash
# backup-config.sh

BACKUP_DIR="backups/$(date +%Y-%m-%d)"
mkdir -p $BACKUP_DIR

# Export CloudFormation templates
aws cloudformation get-template \
  --stack-name iam-rotator-orchestrator \
  --query 'TemplateBody' > $BACKUP_DIR/orchestrator.yaml

aws cloudformation get-template \
  --stack-name iam-rotator-rotation \
  --query 'TemplateBody' > $BACKUP_DIR/rotation.yaml

aws cloudformation get-template \
  --stack-name iam-rotator-account-inventory \
  --query 'TemplateBody' > $BACKUP_DIR/inventory.yaml

aws cloudformation get-template \
  --stack-name iam-rotator-notifier \
  --query 'TemplateBody' > $BACKUP_DIR/notifier.yaml

# Export Lambda source code
for FUNC in IAM-Access-Key-Rotation-Function Account-Inventory-Lambda Notifier-Lambda; do
  aws lambda get-function \
    --function-name $FUNC \
    --query 'Code.Location' \
    --region us-east-1 | xargs curl -o $BACKUP_DIR/$FUNC.zip
done

# Export IAM roles
aws iam get-role \
  --role-name iam-key-rotation-lambda-execution-role \
  > $BACKUP_DIR/execution-role.json

tar -czf $BACKUP_DIR.tar.gz $BACKUP_DIR/
echo "✓ Backup completed: $BACKUP_DIR.tar.gz"
```

### Disaster Recovery Plan

1. **Full Stack Restore**:
   - Redeploy all SAM applications
   - Recreate CloudFormation stacks
   - Reapply StackSet deployments

2. **Partial Recovery** (if only Lambda code corrupted):
   - Use deployment package from backup
   - Use `aws lambda update-function-code`

3. **Configuration Recovery**:
   - Restore environment variables
   - Reapply parameter values

## Cost Optimization

### Monitor Lambda Costs

```bash
# Get Lambda compute duration
aws cloudwatch get-metric-statistics \
  --namespace AWS/Lambda \
  --metric-name Duration \
  --dimensions Name=FunctionName,Value=IAM-Access-Key-Rotation-Function \
  --start-time 2026-08-01T00:00:00Z \
  --end-time 2026-08-31T23:59:59Z \
  --period 2592000 \
  --statistics Sum,Average,Maximum
```

**Cost Estimation**:
- **Inventory Lambda**: 1 invocation/day × 5 seconds = 5k invocations/month = ~$0.10
- **Rotation Lambda**: 500 invocations/month × 120 seconds = 60M GB-seconds = ~$1.20
- **Notifier Lambda**: 500 invocations/month × 5 seconds = 2.5M GB-seconds = ~$0.05
- **CloudWatch Events**: $0.10/month
- **SES**: ~$0.10/email = ~$50/month (depends on org size)

**Total**: ~$51.45/month for typical organization

### Optimization Tips

1. Use OU-based targeting to reduce rotation Lambda invocations
2. Increase rotation period from 90 to 180 days (if acceptable)
3. Batch multiple accounts in single Lambda invocation
4. Use SES production email address (cheaper than sandbox)

---

**Document Version**: 2.0  
**Last Updated**: 2026-08-04
