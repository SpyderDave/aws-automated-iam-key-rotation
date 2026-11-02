# Architecture Documentation

## System Architecture Overview

### High-Level Component Diagram

```mermaid
graph TB
    subgraph "Primary Account"
        CWE["CloudWatch Event<br/>(Daily Trigger)"]
        INV["Account Inventory<br/>Lambda"]
        ROT["Access Key Rotation<br/>Lambda"]
        NOT["Notifier<br/>Lambda"]
        SES["AWS SES<br/>(Email Service)"]
        SM["Secrets Manager<br/>(Key Storage)"]
    end
    
    subgraph "Organization"
        ORG["AWS Organizations<br/>(Account Source)"]
    end
    
    subgraph "Member Accounts"
        IAM["IAM Service<br/>(Users & Keys)"]
        ROLE["Assumed Role<br/>(Cross-Account)"]
    end
    
    CWE -->|triggers| INV
    INV -->|queries| ORG
    INV -->|async invoke| ROT
    ROT -->|assume role| ROLE
    ROLE -->|manage keys| IAM
    ROT -->|async invoke| NOT
    NOT -->|send email| SES
    ROT -->|store secrets| SM
    SES -->|email| Email["Account Owner<br/>Email"]
```

### Execution Timeline

```mermaid
sequenceDiagram
    participant CW as CloudWatch<br/>Events
    participant INV as Account<br/>Inventory
    participant ORG as AWS<br/>Organizations
    participant ROT as Rotation<br/>Lambda
    participant IAM as Target Account<br/>IAM
    participant NOT as Notifier<br/>Lambda
    participant SES as SES<br/>Email

    CW->>INV: 1. Trigger (5 AM UTC)
    INV->>ORG: 2. List accounts & tags
    ORG-->>INV: Account list
    loop For each account
        INV->>ROT: 3. Async invoke
        activate ROT
        ROT->>IAM: 4a. Assume role
        ROT->>IAM: 4b. List users & keys
        IAM-->>ROT: User & key data
        ROT->>ROT: 5. Analyze key age
        alt Enforcement Mode
            ROT->>IAM: 6a. Create new key
            ROT->>IAM: 6b. Deactivate old key
            ROT->>IAM: 6c. Delete expired key
        end
        ROT->>NOT: 7. Invoke notifier
        deactivate ROT
    end
    
    activate NOT
    NOT->>SES: 8. Send email
    SES-->>Email: 9. Delivery
    deactivate NOT
```

### Data Flow Diagram

```mermaid
graph LR
    subgraph Input["Input Sources"]
        CW["CloudWatch Event"]
        TEST["Test Event<br/>(Force Rotation)"]
    end
    
    subgraph Processing["Processing Pipeline"]
        INV["Inventory:<br/>Account Discovery"]
        SCAN["Scanner:<br/>Key Analysis"]
        EXEMPT["Exemption:<br/>Group Check"]
        EVAL["Evaluation:<br/>Action Planning"]
        ACTION["Action:<br/>Key Operations"]
    end
    
    subgraph Output["Output & Storage"]
        LOG["CloudWatch<br/>Logs"]
        NOTIFY["Email<br/>Notifications"]
        SECRET["Secrets<br/>Manager"]
    end
    
    CW --> INV
    TEST --> SCAN
    INV --> SCAN
    SCAN --> EXEMPT
    EXEMPT --> EVAL
    EVAL --> ACTION
    ACTION --> LOG
    ACTION --> NOTIFY
    ACTION --> SECRET
```

## Component Details

### 1. Account Inventory Lambda

**Diagram**: Account Discovery Process

```mermaid
graph TD
    START["Start:<br/>Account Inventory"]
    CHECK{"OU ID<br/>Provided?"}
    ALL["List All Accounts<br/>from Organization"]
    OU["List Accounts<br/>from Specific OU"]
    RECURSE["Recursively Process<br/>Child OUs"]
    TAGS["Get Account Tags<br/>from Organization"]
    FILTER["Filter:<br/>Active Accounts Only"]
    BUILD["Build JSON Payload<br/>with Account Details"]
    INVOKE["Async Invoke<br/>Rotation Lambda"]
    END["Complete"]
    
    START --> CHECK
    CHECK -->|Yes| OU
    CHECK -->|No| ALL
    ALL --> TAGS
    OU --> RECURSE
    RECURSE --> TAGS
    TAGS --> FILTER
    FILTER --> BUILD
    BUILD --> INVOKE
    INVOKE --> END
```

**Key Features**:
- Pagination support for large organizations (20+ accounts per page)
- Recursive OU traversal for nested organizational structures
- Automatic exclusion of suspended accounts
- Tag retrieval for account-level policy overrides
- Asynchronous Lambda invocation (Event trigger type)

**Configuration**:
- `LambdaRotationFunction`: Target Lambda ARN
- `InventoryOU`: Optional OU ID filter (empty = all accounts)

### 2. Access Key Rotation Lambda

**Diagram**: Core Rotation Logic

```mermaid
graph TD
    START["Start:<br/>Rotation Lambda"]
    PAYLOAD["Parse Event:<br/>Account ID, Email, Tags"]
    DRYRUN{"Check DryRun<br/>Flag"}
    TAG_OVERRIDE{"Account Tag:<br/>iamRotationPolicy?"}
    MODE["Set Mode:<br/>Audit or Enforce"]
    ASSUME["Assume Cross-<br/>Account Role"]
    LIST["List IAM Users<br/>& Access Keys"]
    SCAN["Scan Key Age<br/>& Usage"]
    EXEMPT["Check Exemption<br/>Group"]
    FORCE["Check Force<br/>Rotation"]
    ACTION["Build Action<br/>Queue"]
    LOG_ACT["Log Actions<br/>to CloudWatch"]
    
    EXECUTE{"Mode =<br/>Enforce?"}
    EXE_ACT["Execute Actions:<br/>Create/Deactivate/Delete"]
    SKIP["Skip Execution<br/>Audit Only"]
    
    NOTIFY["Invoke Notifier<br/>Lambda"]
    END["Complete"]
    
    START --> PAYLOAD
    PAYLOAD --> DRYRUN
    DRYRUN -->|Config Flag| TAG_OVERRIDE
    TAG_OVERRIDE -->|Yes| MODE
    TAG_OVERRIDE -->|No| MODE
    MODE --> ASSUME
    ASSUME --> LIST
    LIST --> SCAN
    SCAN --> EXEMPT
    EXEMPT --> FORCE
    FORCE --> ACTION
    ACTION --> LOG_ACT
    LOG_ACT --> EXECUTE
    EXECUTE -->|True| EXE_ACT
    EXECUTE -->|False| SKIP
    EXE_ACT --> NOTIFY
    SKIP --> NOTIFY
    NOTIFY --> END
```

**Key Modules**:

- **sts_connection_handler.py**: Cross-account role assumption
- **account_scan.py**: Key age analysis and action determination
- **key_actions.py**: Lifecycle operations (create, deactivate, delete)
- **exemption_handler.py**: IAM group exemption validation
- **force_rotation_handler.py**: Emergency rotation triggers
- **notification_handler.py**: Notifier Lambda invocation

**Action Determination Logic**:

```mermaid
graph TD
    KEY["Access Key"]
    AGE["Calculate Age"]
    LAST_USED["Get Last Used Date"]
    EXP_DATE["Calculate Expiration<br/>Create + RotationPeriod"]
    
    NOW["Current Time"]
    
    ROTATION_WARN["Now >= ExpDate - 7d<br/>AND Now < ExpDate?"]
    ROTATION_DUE["Now >= ExpDate?"]
    INACTIVE_WARN["Now >= InactiveDate - 7d<br/>AND < InactiveDate?"]
    INACTIVE_DUE["Now >= InactiveDate?"]
    UNUSED["Never Used?"]
    
    ACTION_PEND_ROT["Action:<br/>PENDING_ROTATION"]
    ACTION_ROTATE["Action:<br/>ROTATE"]
    ACTION_PEND_DEACT["Action:<br/>PENDING_DEACTIVATION"]
    ACTION_DEACT["Action:<br/>DEACTIVATE"]
    ACTION_PEND_DEL["Action:<br/>PENDING_DELETION"]
    ACTION_DEL["Action:<br/>DELETE"]
    ACTION_UNUSED_EXP["Action:<br/>UNUSED_EXPIRED"]
    
    KEY --> AGE
    KEY --> LAST_USED
    AGE --> EXP_DATE
    EXP_DATE --> NOW
    NOW --> ROTATION_WARN
    ROTATION_WARN -->|Yes| ACTION_PEND_ROT
    ROTATION_WARN -->|No| ROTATION_DUE
    ROTATION_DUE -->|Yes| ACTION_ROTATE
    ROTATION_DUE -->|No| INACTIVE_WARN
    INACTIVE_WARN -->|Yes| ACTION_PEND_DEACT
    INACTIVE_WARN -->|No| INACTIVE_DUE
    INACTIVE_DUE -->|Yes| ACTION_DEACT
    INACTIVE_DUE -->|No| UNUSED
    UNUSED -->|Yes| ACTION_UNUSED_EXP
    UNUSED -->|No| ACTION_PEND_DEL
```

**Default Time Configuration**:

| Phase | Duration | Default | Description |
|-------|----------|---------|-------------|
| RotationPeriod | Days | 90 | Time from key creation to rotation |
| InstallationGracePeriod | Days | 7 | Time to install new key after rotation |
| PendingActionWarnPeriod | Days | 7 | Days ahead to warn of pending action |
| RecoveryGracePeriod | Days | 7 | Time for recovery after deactivation |

**Timeline Example** (90-day rotation, 7-day grace periods):

```
Day 0:     Key Created
Day 83:    Warning: Key will rotate in 7 days
Day 90:    ROTATION: New key created, old key deactivated
Day 97:    Warning: Key will be deleted in 7 days
Day 100:   DELETION: Key permanently removed
```

### 3. Notifier Lambda

**Diagram**: Email Notification Process

```mermaid
graph TD
    START["Start:<br/>Notifier Lambda"]
    PARSE["Parse Event:<br/>Email, Template, Values"]
    TEMPLATE["Load Email Template<br/>from S3"]
    POPULATE["Populate Template<br/>with Values"]
    BUILD_EMAIL["Build Email:<br/>Sender, Recipients, Body"]
    SES["Send via SES"]
    
    SUCCESS{"Send<br/>Success?"}
    LOG_SUCCESS["Log: Email Sent"]
    LOG_FAIL["Log: Email Failed"]
    ERROR["Handle Error:<br/>Retry/Alert"]
    
    COMPLETE["Complete"]
    
    START --> PARSE
    PARSE --> TEMPLATE
    TEMPLATE --> POPULATE
    POPULATE --> BUILD_EMAIL
    BUILD_EMAIL --> SES
    SES --> SUCCESS
    SUCCESS -->|Yes| LOG_SUCCESS
    SUCCESS -->|No| LOG_FAIL
    LOG_SUCCESS --> COMPLETE
    LOG_FAIL --> ERROR
    ERROR --> COMPLETE
```

**Email Template Variables**:

```json
{
  "account_id": "123456789012",
  "account_name": "production-account",
  "timestamp": "04/08/2026 05:30:00",
  "actions": "[...list of actions...]",
  "sender_email": "ops@company.com"
}
```

**Email Templates**:

1. **iam-auto-key-rotation-audit.html** (Audit Mode)
   - Shows keys that would be rotated
   - No actual actions taken
   - For compliance reporting

2. **iam-auto-key-rotation-enforcement.html** (Enforcement Mode)
   - Shows keys that were rotated
   - Lists new key IDs (partial)
   - Prompts for credential installation

### 4. Security Architecture

**Diagram**: IAM Permission Model

```mermaid
graph TB
    PRIMARY["Primary Account<br/>iam-key-rotator"]
    MEMBER["Member Account<br/>in Organization"]
    
    subgraph "Primary Account"
        LAMBDA["Lambda Execution<br/>Role"]
        LAMBDA_PERMS["Permissions:<br/>- AssumeRole *<br/>- InvokeFunction<br/>- CloudWatch Logs"]
    end
    
    subgraph "Member Account"
        ASSUME_ROLE["Assumed Role<br/>iam-key-rotation-...<br/>assumed-role"]
        ASSUME_PERMS["Permissions:<br/>- IAM List*<br/>- CreateAccessKey<br/>- UpdateAccessKey<br/>- DeleteAccessKey<br/>- SecretsManager *"]
    end
    
    subgraph "Condition"
        CONDITION["Condition:<br/>aws:PrincipalOrgID<br/>= org-id"]
    end
    
    LAMBDA -->|AssumeRole| ASSUME_ROLE
    ASSUME_ROLE -->|governed by| CONDITION
    LAMBDA_PERMS -.-> LAMBDA
    ASSUME_PERMS -.-> ASSUME_ROLE
```

**Trust Relationship**:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "AWS": "arn:aws:iam::PRIMARY_ACCOUNT:role/lambda-execution-role"
      },
      "Action": "sts:AssumeRole",
      "Condition": {
        "StringEquals": {
          "aws:PrincipalOrgID": "o-xxxxxxxxxx"
        }
      }
    }
  ]
}
```

## Deployment Architecture

### Orchestration

```mermaid
graph LR
    START["Start<br/>Deployment"]
    
    BUILD["Build SAM<br/>Applications"]
    
    NOTIFIER["Deploy<br/>Notifier<br/>Lambda"]
    INVENTORY["Deploy<br/>Inventory<br/>Lambda"]
    ROTATION["Deploy<br/>Rotation<br/>Lambda"]
    
    MAIN_CF["Deploy Main<br/>CloudFormation<br/>Stack"]
    
    STACKSET["Deploy<br/>Cross-Account<br/>StackSet"]
    
    VERIFY["Verify<br/>Deployment"]
    COMPLETE["Complete"]
    
    START --> BUILD
    BUILD --> NOTIFIER
    BUILD --> INVENTORY
    BUILD --> ROTATION
    NOTIFIER --> MAIN_CF
    INVENTORY --> MAIN_CF
    ROTATION --> MAIN_CF
    MAIN_CF --> STACKSET
    STACKSET --> VERIFY
    VERIFY --> COMPLETE
```

### Stack Dependencies

```mermaid
graph TD
    BASE["Prerequisites:<br/>AWS Organizations<br/>SES Configuration"]
    
    N["Notifier Lambda<br/>Stack"]
    INV["Inventory Lambda<br/>Stack"]
    ROT["Rotation Lambda<br/>Stack"]
    
    MAIN["Main Orchestration<br/>Stack<br/>- CloudWatch Rules<br/>- Permissions"]
    
    SS["Cross-Account<br/>StackSet<br/>- Assumed Roles<br/>- Exemption Groups"]
    
    BASE --> N
    BASE --> INV
    BASE --> ROT
    N --> MAIN
    INV --> MAIN
    ROT --> MAIN
    MAIN --> SS
```

## Data Models

### Account Inventory Event

```json
{
  "account": "123456789012",
  "name": "production-account",
  "email": "account-owner@company.com",
  "tags": {
    "iamRotationPolicy": "Strict",
    "Environment": "Production"
  }
}
```

### Action Queue Item

```json
{
  "UserName": "john.doe",
  "AccessKeyId": "AKIAIOSFODNN7EXAMPLE",
  "CreateDate": "2025-09-04T10:30:00Z",
  "LastUsedDate": "2026-06-15T14:22:00Z",
  "ExpireDate": "2025-12-03T10:30:00Z",
  "Action": "ROTATE",
  "Reason": "Active key has expired",
  "DaysOld": 93,
  "DaysUntilExpire": -11
}
```

### Notification Event

```json
{
  "email": "account-owner@company.com",
  "subject": "IAM Key Rotation Report - 2026-08-04",
  "email_template": "iam-auto-key-rotation-enforcement.html",
  "template_values": {
    "account_id": "123456789012",
    "account_name": "production-account",
    "timestamp": "04/08/2026 05:30:00",
    "actions": "[{...actions...}]"
  }
}
```

## Operational Flows

### Normal Execution Flow

```mermaid
graph TD
    T["5 AM UTC Monday"]
    T -->|CloudWatch Event| INV["Account Inventory<br/>Lambda"]
    
    INV --> QUERY["Query AWS Organizations<br/>for all accounts"]
    QUERY --> LOOP["For Each Active Account"]
    
    LOOP --> INVOKE["Async Invoke<br/>Rotation Lambda"]
    INVOKE --> ROT["Rotation Lambda<br/>Processes Account"]
    
    ROT --> ASSUME["Assume Cross-<br/>Account Role"]
    ASSUME --> SCAN["Scan IAM Users<br/>& Keys"]
    SCAN --> EVAL["Evaluate Rotation<br/>Actions"]
    
    EVAL --> DRYRUN{"Dry-Run<br/>Mode?"}
    
    DRYRUN -->|Yes| REPORT["Report Actions<br/>to Email"]
    DRYRUN -->|No| EXECUTE["Execute Actions:<br/>Create/Deactivate/Delete"]
    EXECUTE --> REPORT
    
    REPORT --> NOTIFY["Async Invoke<br/>Notifier Lambda"]
    NOTIFY --> EMAIL["Send Email<br/>to Account Owner"]
    EMAIL --> NEXT["Next Account"]
    
    NEXT --> LOOP
    LOOP --> COMPLETE["Complete"]
```

### Force Rotation Flow

```mermaid
graph TD
    TEST["Manual Test Event"]
    TEST --> PAYLOAD["Payload:<br/>force_rotate_users"]
    PAYLOAD --> ROT["Rotation Lambda<br/>Receives Event"]
    ROT --> CHECK["Check force_rotate<br/>Users List"]
    CHECK --> FORCE["Force Rotation<br/>of Listed Users"]
    FORCE --> EXECUTE["Execute Immediately<br/>Skip Age Checks"]
    EXECUTE --> EMAIL["Send Email<br/>Confirmation"]
    EMAIL --> DONE["Complete"]
```

### Emergency Exemption Flow

```mermaid
graph TD
    INCIDENT["Security Incident<br/>or Service Account"]
    INCIDENT --> ADD_GROUP["Add User to<br/>Exemption Group"]
    ADD_GROUP --> IAM["AWS IAM<br/>Update Group"]
    IAM --> WAIT["Wait for<br/>Next Rotation"]
    WAIT --> SKIP["User Skipped<br/>in Next Run"]
    SKIP --> RESOLVE["Issue Resolved"]
    RESOLVE --> REMOVE["Remove User from<br/>Exemption Group"]
    REMOVE --> RESUME["Resume Rotation<br/>Next Cycle"]
```

## Scalability Considerations

### Supported Scale

```mermaid
graph LR
    SMALL["< 50 Accounts<br/>Standard Config"]
    MEDIUM["50-500 Accounts<br/>Default Config"]
    LARGE["500-5000 Accounts<br/>OU-Based Targeting<br/>Increased Timeout"]
    XLARGE["5000+ Accounts<br/>Multiple StackSets<br/>Regional Split"]
    
    SMALL --> MEDIUM
    MEDIUM --> LARGE
    LARGE --> XLARGE
```

### Performance Tuning

| Setting | Default | Large Org | XL Org |
|---------|---------|-----------|--------|
| Lambda Timeout | 400s | 600s | 900s |
| Concurrent Executions | Account Count | 1000+ | 5000+ |
| OU Targeting | All | Selective | Multi-wave |
| Batch Size | N/A | Async Event | Event batching |

---

**Document Version**: 2.0  
**Last Updated**: 2026-08-04
