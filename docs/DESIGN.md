# Design & Features Documentation

## Design Philosophy

### Core Principles

1. **Security First**: All operations assume least-privilege access with condition-based restrictions
2. **Auditability**: Every action is logged and traceable for compliance
3. **Operational Safety**: Dual-mode operation (audit/enforce) allows safe deployment
4. **Organization Native**: Leverages AWS Organizations for account discovery and hierarchical control
5. **Extensibility**: Modular Lambda functions allow independent updates and testing
6. **Cost Efficiency**: Serverless architecture with minimal fixed costs

## Key Features

### 1. Multi-Account Support

**Design**: Cross-account IAM role assumption enables centralized management

```
Primary Account (Rotator)
    ↓ AssumeRole
Member Account A (Assumed Role)
    ↓ AssumeRole  
Member Account B (Assumed Role)
    ↓ AssumeRole
Member Account C (Assumed Role)
```

**Benefits**:
- Single Lambda function manages all accounts
- Centralized logging and monitoring
- Simplified credential management (only primary account credentials needed)
- Scalable to organizations with 100+ accounts

**Implementation**:
- StackSet deploys assumed roles to all member accounts
- Trust relationship restricted by `aws:PrincipalOrgID` condition
- Automatic opt-in for new accounts (if auto-deployment enabled)

### 2. Dual Operating Modes

#### Audit Mode (DryRun=True)

**Purpose**: Analyze and report without making changes

**Behavior**:
- Lists all IAM users and keys
- Calculates rotation actions
- **Does NOT create new keys**
- **Does NOT deactivate keys**
- **Does NOT delete keys**
- Sends email reports with audit findings

**Use Cases**:
- Pre-deployment validation
- Compliance reporting
- Risk assessment
- Policy testing

**Example Email Output**:
```
Found 5 keys to rotate in account production:
- john.doe AKIAIOSFODNN7EXAMPLE (Created 94 days ago) → ROTATE
- jane.smith AKIAIOSFODNN8EXAMPLE (Created 97 days ago) → ROTATE
- service.account AKIAIOSFODNN9EXAMPLE (Created 185 days ago) → DELETE
```

#### Enforcement Mode (DryRun=False)

**Purpose**: Execute full key rotation lifecycle

**Behavior**:
- Creates new access keys
- Deactivates expired keys
- Deletes deactivated keys
- Updates IAM user policies
- Stores secrets in Secrets Manager
- Sends email reports with action confirmation

**Use Cases**:
- Production compliance enforcement
- Automated key lifecycle management
- Credential hygiene maintenance

**Example Email Output**:
```
Rotated 5 keys in account production:
- john.doe: New key AKIA... created, old key AKIAIOSFODNN7EXAMPLE deactivated
- jane.smith: New key AKIA... created, old key AKIAIOSFODNN8EXAMPLE deactivated
- service.account: Key AKIAIOSFODNN9EXAMPLE permanently deleted
```

### 3. Hierarchical Control

#### Global Control (DryRunFlag)

The default mode for all accounts:

```yaml
DryRunFlag: True   # All accounts run in audit mode
DryRunFlag: False  # All accounts run in enforcement mode
```

#### Account-Level Override (Tags)

AWS Organization account tags override global setting:

```bash
# Force enforcement for specific account
aws organizations tag-resource \
  --resource-id 123456789012 \
  --tags Key=iamRotationPolicy,Value=Strict
```

**Precedence Logic**:

```python
# From main.py
if tags.get('iamRotationPolicy') == 'Strict':
    dryrun = False  # Force enforcement
else:
    dryrun = True   # Force audit mode
```

This enables:
- Gradual rollout (tag production accounts for enforcement first)
- Account-specific policies (different rules per environment)
- Selective remediation (rotate only compromised accounts)

#### OU-Level Control (Inventory OU)

The Account Inventory Lambda can target specific organizational units:

```bash
aws lambda update-function-configuration \
  --function-name Account-Inventory-Lambda \
  --environment Variables="{
    LambdaRotationFunction=arn:...,
    InventoryOU=ou-xxxx-aaaaaaaa
  }"
```

**Benefits**:
- Process large organizations in waves
- Separate production and non-production schedules
- Reduce Lambda execution time
- Fine-grained compliance per OU

### 4. Exemption Management

**Design**: IAM group-based exemption mechanism

**How It Works**:

```
User
  ↓ Check if member of
IAMKeyRotationExemptionGroup
  ↓ If YES
Skip rotation, notify ops
  ↓ If NO
Proceed with rotation logic
```

**Use Cases**:
- Service accounts with manual key rotation
- Accounts with external key dependencies
- Applications with key caching
- Temporary exemptions during maintenance

**Scope**: Account-level (each account manages own exemptions)

**Example**:

```bash
# Exempt service account in target account
# (requires cross-account assumption)
aws iam add-user-to-group \
  --group-name IAMKeyRotationExemptionGroup \
  --user-name database-service-account

# Logs show:
# "Skipping user: database-service-account (exempted)"
```

### 5. Key Lifecycle Management

#### State Machine

```mermaid
graph TD
    NEW["Key Created<br/>(Day 0)"]
    
    PENDING_ROT["Key Pending<br/>Rotation<br/>(Day 83)"]
    
    ROTATED["Key Rotated<br/>(Day 90)"]
    
    PENDING_DEACT["Key Pending<br/>Deactivation<br/>(Day 97)"]
    
    DEACTIVATED["Key Deactivated<br/>(Day 100)"]
    
    PENDING_DEL["Key Pending<br/>Deletion<br/>(Day 107)"]
    
    DELETED["Key Deleted<br/>(Day 114)"]
    
    NEW -->|"Email warning<br/>@Day 83"| PENDING_ROT
    PENDING_ROT -->|"Execute rotation<br/>@Day 90"| ROTATED
    ROTATED -->|"Email warning<br/>@Day 97"| PENDING_DEACT
    PENDING_DEACT -->|"Deactivate<br/>@Day 100"| DEACTIVATED
    DEACTIVATED -->|"Email warning<br/>@Day 107"| PENDING_DEL
    PENDING_DEL -->|"Delete<br/>@Day 114"| DELETED
```

#### Default Timeline (90-day rotation)

| Day | Event | Action | Notes |
|-----|-------|--------|-------|
| 0 | Key Created | System | Initial state |
| 83 | PENDING_ROTATION | Email Warning | "7 days until rotation" |
| 90 | ROTATE | Create new key, deactivate old | Installation window opens |
| 97 | PENDING_DEACTIVATION | Email Warning | "7 days until deactivation" |
| 100 | DEACTIVATE | Mark as inactive | Unusable after this |
| 107 | PENDING_DELETION | Email Warning | "7 days until deletion" |
| 114 | DELETE | Permanently remove | Irreversible |

#### Customization

All timelines are configurable:

```bash
# 180-day rotation with 14-day grace periods
aws cloudformation update-stack \
  --stack-name iam-rotator-rotation \
  --parameters \
    ParameterKey=RotationPeriod,ParameterValue=180 \
    ParameterKey=InactiveBuffer,ParameterValue=14 \
    ParameterKey=RecoveryGracePeriod,ParameterValue=14 \
    ParameterKey=PendingActionWarnPeriod,ParameterValue=14
```

### 6. Conflict Resolution

When multiple keys exist (common for safe key rotation):

```
User: john.doe
├─ Key 1 (Active, 91 days old) → ROTATE
└─ Key 2 (Inactive, 10 days old) → KEEP

Action: Only rotate the active key
Result: User now has 1 new active key + 1 old inactive key
```

**Algorithm**:

```python
def determine_action(keys):
    for key in keys:
        if key.is_active:
            if key.age > rotation_period:
                return ACTION.ROTATE  # Create new, deactivate this
            elif key.age > rotation_period - warn_period:
                return ACTION.PENDING_ROTATION  # Warn user
        else:
            if key.age > inactive_period:
                return ACTION.DELETE  # Safe to remove
            elif key.age > inactive_period - warn_period:
                return ACTION.PENDING_DELETION  # Warn before delete
```

**Safety**:
- Never deletes active keys
- Always maintains one key for access
- Grace periods prevent accidental lockout
- Inactive keys kept for recovery window

### 7. Secrets Manager Integration

**Purpose**: Secure new key storage for user retrieval

**Workflow**:

```
Lambda creates new access key
    ↓
Lambda creates secret in Secrets Manager
    ↓
New key stored as: {"AccessKeyId": "AKIA...", "SecretAccessKey": "..."}
    ↓
IAM policy attached to user to read secret
    ↓
User retrieves via: aws secretsmanager get-secret-value
```

**Secret Naming**:

```
Format: User_{USERNAME}_AccessKey
Example: User_john.doe_AccessKey
```

**Access Control**:

```json
{
  "Effect": "Allow",
  "Principal": {"AWS": "arn:aws:iam::account:user/john.doe"},
  "Action": [
    "secretsmanager:GetSecretValue",
    "secretsmanager:DescribeSecret"
  ],
  "Resource": "arn:aws:secretsmanager:region:account:secret:User_john.doe_AccessKey*"
}
```

**Encryption**:
- Default: AWS managed key (aws/secretsmanager)
- Optional: Customer managed KMS key for enhanced control

**Retention**:
- 7 days (default) before secret auto-rotation
- User can retrieve new key immediately
- Old secret version accessible for 7 days

### 8. Force Rotation

**Purpose**: Emergency key rotation for compromised credentials

**Trigger**: Test Lambda event with `force_rotate_users` list

**Example**:

```json
{
  "account": "123456789012",
  "name": "production-account",
  "email": "owner@company.com",
  "dryrun": false,
  "force_rotate_users": ["compromised.user"],
  "tags": {}
}
```

**Behavior**:
- Ignores key age requirements
- Rotates immediately regardless of grace periods
- Sends priority email notification
- Logs emergency rotation flag

**Use Cases**:
- Credential compromise detected
- Malicious access suspected
- Automated breach response
- Audit required rotations

### 9. Comprehensive Logging

All operations logged to CloudWatch for audit trail:

```
[INFO] Function starting
[INFO] Currently evaluating Account ID: 123456789012 | Account Name: production
[INFO] Dryrun is set to: False
[INFO] Processing user: john.doe
[INFO] Key AKIAIOSFODNN7EXAMPLE: Age 91 days → ACTION: ROTATE
[INFO] Creating new access key for john.doe
[INFO] New key created: AKIA... (SecretAccessKey truncated)
[INFO] Storing secret in Secrets Manager: User_john.doe_AccessKey
[INFO] Deactivating old key: AKIAIOSFODNN7EXAMPLE
[INFO] Invoking notifier Lambda
[INFO] Function has completed
```

**Log Retention**:
- Default: 30 days
- Configurable via CloudWatch Logs policy

**Search Examples**:

```bash
# Find all rotations in past week
aws logs filter-log-events \
  --log-group-name /aws/lambda/IAM-Access-Key-Rotation-Function \
  --filter-pattern "ACTION: ROTATE" \
  --start-time $(($(date +%s) - 604800))

# Find errors
aws logs filter-log-events \
  --log-group-name /aws/lambda/IAM-Access-Key-Rotation-Function \
  --filter-pattern "ERROR"

# Find specific user activity
aws logs filter-log-events \
  --log-group-name /aws/lambda/IAM-Access-Key-Rotation-Function \
  --filter-pattern "john.doe"
```

## Security Design

### Principle of Least Privilege

**Primary Account Lambda Execution Role**:
```json
{
  "Effect": "Allow",
  "Action": "sts:AssumeRole",
  "Resource": "arn:aws:iam::*:role/iam-key-rotation-lambda-assumed-role",
  "Condition": {
    "StringEquals": {"aws:PrincipalOrgID": "o-xxxxxxxxxx"}
  }
}
```

- Can ONLY assume specific role name
- Restricted to organization members (PrincipalOrgID condition)
- Cannot access other AWS services directly

**Member Account Assumed Role**:
```json
{
  "Effect": "Allow",
  "Action": [
    "iam:List*",
    "iam:CreateAccessKey",
    "iam:UpdateAccessKey",
    "iam:DeleteAccessKey"
  ],
  "Resource": "*"
}
```

- Limited to IAM operations only
- No compute, networking, or storage access
- Cannot escalate privileges beyond IAM management

### Data Protection

1. **At Rest**:
   - Access keys stored in Secrets Manager with encryption
   - Default: AWS managed encryption
   - Optional: Customer managed KMS keys

2. **In Transit**:
   - All AWS API calls use HTTPS
   - Encrypted Lambda environment variables
   - No keys logged to CloudWatch

3. **Access Control**:
   - New key secrets readable only by corresponding user
   - IAM resource policies enforce least-privilege
   - Temporary credentials from STS for cross-account access

### Audit Trail

Every action recorded:

```
AWS CloudTrail       → Logs all API calls to CloudFormation, IAM, STS
Lambda Logs          → Application-level logging
Secrets Manager      → Automatic key rotation audit
Organizations        → Account and tag changes
```

Searchable by:
- Account ID
- User name
- Key ID
- Timestamp
- Action type

## Extensibility Points

### Custom Action Handlers

Extend rotation logic for specialized scenarios:

```python
# In key_actions.py
def handle_custom_action(key_metadata, custom_reason):
    """Example extension point"""
    if custom_reason == "REGULATORY_AUDIT":
        # Force rotation regardless of age
        rotate_key(key_metadata)
    elif custom_reason == "COMPLIANCE_SNAPSHOT":
        # Report without modifying
        log_action(key_metadata, ACTION.AUDIT)
```

### Custom Exemption Logic

Replace IAM group with database lookup:

```python
# In exemption_handler.py
def validate_exemption_group(user_name):
    # Current: Check IAM group membership
    group_members = iam.get_group(GroupName=config.exemption_group)
    return user_name in [u['UserName'] for u in group_members['Users']]
    
    # Alternative: Query exemption database
    # db_conn = get_exemption_db()
    # return db_conn.query("SELECT * FROM exemptions WHERE user = ?", user_name)
```

### Custom Email Templates

Create organization-specific templates:

```html
<!-- email-template/custom-enforcement.html -->
<html>
  <body>
    <h1>Security Alert: IAM Key Rotation</h1>
    <p>Dear Account Owner,</p>
    <p>The following access keys have been rotated for security compliance:</p>
    <!-- Template variables replaced at runtime -->
    {actions}
    <p>New credentials available in Secrets Manager: User_{username}_AccessKey</p>
    <!-- Custom footer -->
    <footer>Contact: security-team@company.com</footer>
  </body>
</html>
```

Upload and configure:

```bash
aws s3 cp custom-enforcement.html s3://templates/custom-enforcement.html
aws lambda update-function-configuration \
  --function-name IAM-Access-Key-Rotation-Function \
  --environment Variables="{EmailTemplateEnforce=custom-enforcement.html}"
```

## Performance Characteristics

### Execution Time

| Operation | Typical Duration | Variability |
|-----------|------------------|-------------|
| Inventory Lambda | 15-30 seconds | ±5 seconds |
| Per-account Rotation | 10-60 seconds | +Number of users |
| Notifier Lambda | 3-5 seconds | ±2 seconds |
| **Total per 100 accounts** | **15-30 minutes** | **Parallel** |

### Scaling Characteristics

```
Account Count: 10-50
    └─ All-in-one execution: 5 min
    └─ Memory: 256 MB sufficient
    └─ Timeout: 400 sec sufficient

Account Count: 50-500
    └─ Sequential account processing: 30 min
    └─ Memory: 512 MB recommended
    └─ Timeout: 600 sec recommended

Account Count: 500-5000
    └─ OU-based wave processing: 10 min per wave
    └─ Memory: 1024 MB recommended
    └─ Timeout: 900 sec for large OUs
    └─ Concurrent executions: 1000+
```

## Compliance

### Standards Covered

1. **CIS AWS Foundations Benchmark**
   - 1.2: Ensure MFA is enabled for all IAM users
   - 1.5: Ensure access keys are rotated every 90 days (configurable)

2. **PCI DSS**
   - Requirement 8.2.3: Change user passwords/passphrases at least every 90 days

3. **NIST Cybersecurity Framework**
   - Detect: Continuous monitoring of key age
   - Respond: Automated remediation of non-compliant credentials

4. **SOC 2**
   - CC6.1: Logical access control enforcement
   - CC6.2: Access management during user lifecycle

5. **HIPAA**
   - 164.312(a)(2)(i): Access management and accountability
   - 164.312(b): Audit and accountability controls

### Compliance Reports

Generate automated compliance evidence:

```bash
aws logs filter-log-events \
  --log-group-name /aws/lambda/IAM-Access-Key-Rotation-Function \
  --filter-pattern "ROTATE|DEACTIVATE|DELETE" \
  --start-time $(($(date +%s) - 86400 * 90)) \
  > rotation-audit-trail.log
```

---

**Document Version**: 2.0  
**Last Updated**: 2026-08-04
