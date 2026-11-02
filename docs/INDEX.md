# Documentation Index

Complete reference guide for the AWS IAM Key Auto-Rotation and Notifier Solution.

## 📚 Documentation Organization

### Getting Started

1. **[QUICK_START.md](./QUICK_START.md)** ⭐ START HERE
   - 5-minute overview
   - 15-minute quick deploy
   - Common commands
   - Troubleshooting quick fixes
   - **Best for**: First-time users, rapid deployment

2. **[README.md](../README.md)** 
   - Complete solution overview
   - All features explained
   - Deployment procedures
   - Configuration guide
   - Usage examples
   - Troubleshooting guide
   - **Best for**: Reference, comprehensive understanding

### Architecture & Design

3. **[ARCHITECTURE.md](./ARCHITECTURE.md)**
   - System architecture diagrams
   - Component interactions (mermaid diagrams)
   - Execution flow diagrams
   - Data flow diagrams
   - Security architecture
   - Deployment architecture
   - Scalability considerations
   - **Best for**: Architects, designing integrations

4. **[DESIGN.md](./DESIGN.md)**
   - Design philosophy & principles
   - Feature explanations
   - Key lifecycle management
   - Operational modes deep-dive
   - Conflict resolution algorithms
   - Extensibility points
   - Performance characteristics
   - Compliance mappings
   - **Best for**: Engineers, understanding decisions

### Implementation & Operations

5. **[IMPLEMENTATION.md](./IMPLEMENTATION.md)**
   - Pre-implementation checklist
   - Step-by-step deployment
   - AWS prerequisites
   - SAM deployment guide
   - CloudFormation deployment
   - StackSet configuration
   - Testing procedures
   - Rollback procedures
   - **Best for**: DevOps, first-time deployment

6. **[OPERATIONS.md](./OPERATIONS.md)**
   - Daily monitoring
   - Operational tasks
   - Troubleshooting guide
   - Performance tuning
   - Backup & recovery
   - Cost optimization
   - Operational scripts
   - **Best for**: Operations team, on-call engineers

## 🎯 Quick Navigation by Role

### I'm deploying this for the first time

1. **Read**: [QUICK_START.md](./QUICK_START.md) (15 min)
2. **Read**: [IMPLEMENTATION.md](./IMPLEMENTATION.md) (30 min)
3. **Do**: Follow deployment steps
4. **Reference**: [README.md](../README.md) for details

### I need to understand the architecture

1. **Read**: [ARCHITECTURE.md](./ARCHITECTURE.md)
2. **Reference**: Mermaid diagrams for visual understanding
3. **Deep-dive**: [DESIGN.md](./DESIGN.md) for feature details

### I'm operating this in production

1. **Read**: [OPERATIONS.md](./OPERATIONS.md)
2. **Keep**: Operational scripts for common tasks
3. **Reference**: [README.md](../README.md) troubleshooting section
4. **Use**: Health check scripts for monitoring

### I need to troubleshoot an issue

1. **Check**: [QUICK_START.md](./QUICK_START.md) Troubleshooting section
2. **Reference**: [README.md](../README.md) Troubleshooting section
3. **Deep-dive**: [OPERATIONS.md](./OPERATIONS.md) Troubleshooting guide
4. **Review**: CloudWatch Logs for details

### I want to customize or extend the solution

1. **Read**: [DESIGN.md](./DESIGN.md) Extensibility section
2. **Reference**: [ARCHITECTURE.md](./ARCHITECTURE.md) for component structure
3. **Review**: [README.md](../README.md) for current behavior

## 📋 Feature Index

### Key Lifecycle

- **Overview**: [README.md#Key Features](../README.md#key-features)
- **Design**: [DESIGN.md#Key Lifecycle Management](./DESIGN.md#5-key-lifecycle-management)
- **Timeline Example**: [DESIGN.md#Timeline Example](./DESIGN.md#timeline-example-90-day-rotation)
- **Customization**: [OPERATIONS.md#Change Rotation Period](./OPERATIONS.md#change-rotation-period)

### Operational Modes (Audit vs Enforce)

- **Overview**: [README.md#Operational Modes](../README.md#operational-modes)
- **Design**: [DESIGN.md#Dual Operating Modes](./DESIGN.md#2-dual-operating-modes)
- **Configuration**: [README.md#Mode 1-3](../README.md#operational-modes)
- **Transition**: [IMPLEMENTATION.md#Step 11](./IMPLEMENTATION.md#step-11-transition-to-enforcement-mode)

### User Exemptions

- **Overview**: [README.md#Exemption Management](../README.md#exemption-management)
- **How It Works**: [DESIGN.md#Exemption Management](./DESIGN.md#4-exemption-management)
- **Add User**: [OPERATIONS.md#Add User to Exemption Group](./OPERATIONS.md#add-user-to-exemption-group)
- **Remove User**: [OPERATIONS.md#Remove User from Exemption Group](./OPERATIONS.md#remove-user-from-exemption-group)
- **Quick Command**: [QUICK_START.md#Exempt User](./QUICK_START.md#exempt-user)

### Email Notifications

- **Overview**: [README.md#Email Notifications](../README.md#email-notifications)
- **Templates**: [OPERATIONS.md#Update Email Templates](./OPERATIONS.md#update-email-templates)
- **Component**: [README.md#Notifier Lambda Function](../README.md#3-notifier-lambda-function)
- **Troubleshooting**: [QUICK_START.md#No emails received](./QUICK_START.md#no-emails-received)

### Cross-Account Management

- **Architecture**: [ARCHITECTURE.md#Cross-Account IAM Trust](./ARCHITECTURE.md#cross-account-iam-trust)
- **Security Model**: [DESIGN.md#Security Design](./DESIGN.md#security-design)
- **Deployment**: [IMPLEMENTATION.md#Step 8](./IMPLEMENTATION.md#step-8-deploy-cross-account-roles-via-stackset)
- **Troubleshooting**: [QUICK_START.md#Cross-account role not found](./QUICK_START.md#cross-account-role-not-found)

### Force Rotation (Emergency)

- **Feature**: [DESIGN.md#Force Rotation](./DESIGN.md#8-force-rotation)
- **How to Use**: [OPERATIONS.md#Force Immediate Rotation](./OPERATIONS.md#force-immediate-rotation)
- **Quick Command**: [QUICK_START.md#Force Rotation](./QUICK_START.md#force-rotation-emergency)

### Secrets Manager Integration

- **Overview**: [README.md#Secret Manager Integration](../README.md#secret-manager-integration)
- **Design**: [DESIGN.md#Secrets Manager Integration](./DESIGN.md#7-secrets-manager-integration)
- **Troubleshooting**: [README.md#Secrets Manager Failures](../README.md#5-secrets-manager-failures)

## 🔧 Configuration Reference

### Parameters

| Parameter | Location | Documentation |
|-----------|----------|-----------------|
| `RotationPeriod` | SAM Template | [README.md#RotationPeriod](../README.md#access-key-rotation-lambda) |
| `DryRunFlag` | Lambda Env | [DESIGN.md#Dual Operating Modes](./DESIGN.md#2-dual-operating-modes) |
| `IAMExemptionGroup` | Lambda Env | [DESIGN.md#Exemption Management](./DESIGN.md#4-exemption-management) |
| `iamRotationPolicy` | Account Tags | [README.md#Account Level Control](../README.md#account-level-control-via-tags) |
| `InventoryOU` | Lambda Env | [OPERATIONS.md#OU-Level Control](./OPERATIONS.md#ou-level-control-inventory-ou) |

### Environment Variables

See [README.md#Configuration](../README.md#configuration) for complete list.

## 🔍 Troubleshooting Map

| Issue | Quick Fix | Reference |
|-------|-----------|-----------|
| No emails | Verify SES setup | [QUICK_START.md#No emails received](./QUICK_START.md#no-emails-received) |
| Cross-account fails | Check StackSet deployment | [README.md#Cross-Account Role Assumption Fails](../README.md#1-cross-account-role-assumption-fails) |
| Lambda timeout | Increase timeout to 600s | [QUICK_START.md#Lambda timeout](./QUICK_START.md#lambda-timeout) |
| Keys not rotating | Check DryRunFlag | [README.md#Keys Not Rotating](../README.md#4-keys-not-rotating-dry-run-always-true) |
| Exemption not working | Verify group name | [QUICK_START.md#Exempt User](./QUICK_START.md#exempt-user) |
| Secrets Manager fails | Check IAM permissions | [README.md#Secrets Manager Failures](../README.md#5-secrets-manager-failures) |

## 📊 Architecture Diagrams

All diagrams use Mermaid and are in [ARCHITECTURE.md](./ARCHITECTURE.md):

1. **System Architecture Overview** - Component relationships
2. **Execution Timeline** - Sequence of operations
3. **Data Flow** - How data moves through system
4. **Account Inventory Process** - Account discovery flow
5. **Rotation Logic** - Key analysis and rotation decision
6. **Email Notification** - Email sending process
7. **IAM Permission Model** - Security architecture
8. **Orchestration** - Deployment order
9. **Cross-Account Trust** - Trust relationships

## 📈 Performance & Scaling

- **Execution Time**: [DESIGN.md#Execution Time](./DESIGN.md#execution-time)
- **Scaling**: [DESIGN.md#Scaling Characteristics](./DESIGN.md#scaling-characteristics)
- **Large Org Tuning**: [OPERATIONS.md#Large Organization](./OPERATIONS.md#large-organization-500-accounts)
- **Cost Optimization**: [OPERATIONS.md#Cost Optimization](./OPERATIONS.md#cost-optimization)

## 🔐 Security & Compliance

- **Security Design**: [DESIGN.md#Security Design](./DESIGN.md#security-design)
- **Least Privilege**: [DESIGN.md#Principle of Least Privilege](./DESIGN.md#principle-of-least-privilege)
- **Data Protection**: [DESIGN.md#Data Protection](./DESIGN.md#data-protection)
- **Audit Trail**: [DESIGN.md#Comprehensive Logging](./DESIGN.md#9-comprehensive-logging)
- **Compliance**: [DESIGN.md#Compliance](./DESIGN.md#compliance)

## 🚀 Quick Commands Reference

### Deployment

```bash
# Quick deploy (see QUICK_START.md)
source QUICK_START.md
./deploy.sh

# Update parameter
aws cloudformation update-stack --stack-name iam-rotator-rotation --parameters ParameterKey=DryRunFlag,ParameterValue=False
```

### Operations

```bash
# Monitor
aws logs tail /aws/lambda/IAM-Access-Key-Rotation-Function --follow

# Force rotation
./force-rotate.sh ACCOUNT_ID USERNAME

# Exempt user
aws iam add-user-to-group --group-name IAMKeyRotationExemptionGroup --user-name USERNAME

# Generate report
./compliance-report.sh
```

See [OPERATIONS.md](./OPERATIONS.md) for complete script library.

### Troubleshooting

```bash
# Check SES setup
aws ses list-verified-email-addresses

# Check role existence
aws iam get-role --role-name iam-key-rotation-lambda-assumed-role

# View recent errors
aws logs filter-log-events \
  --log-group-name /aws/lambda/IAM-Access-Key-Rotation-Function \
  --filter-pattern "ERROR"
```

## 📞 Support Matrix

| Topic | Document | Section |
|-------|----------|---------|
| First deployment | IMPLEMENTATION.md | All sections |
| Architecture explanation | ARCHITECTURE.md | All sections |
| Feature details | DESIGN.md | By feature |
| Daily operations | OPERATIONS.md | All sections |
| Quick reference | QUICK_START.md | All sections |
| Complete reference | README.md | All sections |
| Troubleshooting | Multiple | See [Troubleshooting Map](#troubleshooting-map) |

## 📝 Document Versions & History

- **Version**: 2.0
- **Updated**: 2026-08-04
- **Status**: Production Ready

### Previous Versions

- v1.0: Initial deployment documentation

## 🎓 Learning Path

**Beginner Path** (New to this solution):
1. [QUICK_START.md](./QUICK_START.md) - Overview & quick setup
2. [README.md](../README.md) - Complete reference
3. [ARCHITECTURE.md](./ARCHITECTURE.md) - Visual understanding

**Operator Path** (Running in production):
1. [OPERATIONS.md](./OPERATIONS.md) - Daily tasks
2. [README.md](../README.md#troubleshooting) - Troubleshooting
3. [QUICK_START.md](./QUICK_START.md) - Quick commands

**Architect Path** (Designing or extending):
1. [ARCHITECTURE.md](./ARCHITECTURE.md) - System design
2. [DESIGN.md](./DESIGN.md) - Features & decisions
3. [README.md](../README.md#security) - Security model

**DevOps Path** (Deploying):
1. [QUICK_START.md](./QUICK_START.md) - Quick deploy
2. [IMPLEMENTATION.md](./IMPLEMENTATION.md) - Step-by-step
3. [README.md](../README.md#deployment) - Detailed deployment

## ❓ FAQ Quick Links

**Q: How do I deploy this?**
A: See [QUICK_START.md](./QUICK_START.md) or [IMPLEMENTATION.md](./IMPLEMENTATION.md)

**Q: How does it work?**
A: See [README.md#Overview](../README.md#overview) or [ARCHITECTURE.md](./ARCHITECTURE.md)

**Q: How do I operate this?**
A: See [OPERATIONS.md](./OPERATIONS.md)

**Q: How do I exempt a user?**
A: See [QUICK_START.md#Exempt User](./QUICK_START.md#exempt-user)

**Q: How do I enable enforcement?**
A: See [QUICK_START.md#Enable Enforcement Mode](./QUICK_START.md#enable-enforcement-mode)

**Q: How do I troubleshoot?**
A: See [QUICK_START.md#Troubleshooting](./QUICK_START.md#troubleshooting-quick-fixes) or [README.md#Troubleshooting](../README.md#troubleshooting)

**Q: What's the cost?**
A: See [QUICK_START.md#Cost Estimate](./QUICK_START.md#cost-estimate) or [DESIGN.md#Cost Optimization](./DESIGN.md#cost-optimization)

## 📚 Related Resources

- **AWS Organizations**: https://docs.aws.amazon.com/organizations/
- **IAM Best Practices**: https://docs.aws.amazon.com/IAM/latest/UserGuide/best-practices.html
- **Secrets Manager**: https://docs.aws.amazon.com/secretsmanager/
- **Lambda**: https://docs.aws.amazon.com/lambda/
- **SAM**: https://docs.aws.amazon.com/serverless-application-model/

## 📎 File Structure

```
repository/
├── README.md                          # Main reference document
├── docs/
│   ├── INDEX.md                       # This file
│   ├── QUICK_START.md                 # Quick start guide ⭐
│   ├── ARCHITECTURE.md                # Architecture documentation
│   ├── DESIGN.md                      # Design & features
│   ├── IMPLEMENTATION.md              # Step-by-step deployment
│   ├── OPERATIONS.md                  # Operations & maintenance
├── sam-apps/
│   ├── access-key-auto-rotation/      # Rotation Lambda
│   ├── account-inventory/             # Inventory Lambda
│   └── notifier/                      # Notifier Lambda
├── config/                            # Configuration files
├── templates/                         # CloudFormation templates
├── unit-test/                         # Test events
```

---

**Last Updated**: 2026-08-04  
**Version**: 2.0  
**Status**: Production Ready

For questions or updates, refer to the relevant documentation section above.
