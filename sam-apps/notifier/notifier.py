# (c) 2021 Amazon Web Services, Inc. or its affiliates. All Rights Reserved.
# This AWS Content is provided subject to the terms of the AWS Customer Agreement available at
# https://aws.amazon.com/agreement/ or other written agreement between Customer
# and Amazon Web Services, Inc.

"""Notifier.

Provies core logic for the Notifier Lambda Function.
"""

import logging
import boto3
import os

from botocore.exceptions import ClientError

log = logging.getLogger(__name__)
log.setLevel(logging.INFO)

# Embedded email templates
EMAIL_TEMPLATES = {
    'iam-auto-key-rotation-audit.html': '''<!DOCTYPE html PUBLIC "-//W3C//DTD HTML 4.01//EN" "http://www.w3.org/TR/html4/strict.dtd">
<html>
<head>
  <meta http-equiv="Content-Type" content="text/html; charset=utf-8">
  <meta http-equiv="Content-Style-Type" content="text/css">
  <title></title>
  <style type="text/css">
    p.p1 {margin: 0.0px 0.0px 0.0px 0.0px; font: 12.0px Helvetica; color: #000000; -webkit-text-stroke: #000000}
    p.p2 {margin: 0.0px 0.0px 0.0px 0.0px; font: 12.0px Helvetica; color: #000000; -webkit-text-stroke: #000000; min-height: 14.0px}
    span.s1 {font-kerning: none}
  </style>
</head>
<body>
<p class="p1"><span class="s1">Hello,<br>
<br>
Security is a top priority for us at Your Company. As part of our ongoing security best practices, we are conducting an audit of AWS IAM User Access Keys to ensure compliance.<br>
<br>
Why does this matter to you?<br>
Regular auditing of IAM credentials helps identify potential security risks before they become an issue. This proactive step strengthens our AWS security posture.<br>
<br>
What's changing?<br>
For now, this is just an audit. No IAM Keys will be rotated automatically. You will receive an email if any of your IAM Keys are flagged as non-compliant. This is an opportunity to review and update your credentials accordingly.<br>
<br>
By participating in this audit, you will align with compliance standards such as SOC2, the Center of Internet Security AWS Foundations Benchmark, APRA, MAS, the National Institute of Standards and Technology (NIST), and the AWS Well-Architected Framework.
</span></p>

<br>
<p class="p1"><span class="s1">IAM Access Key in Violation:</span><br>
<p class="p1"><span class="s1">------------------------------------------------------<br>
<p class="p1"><span class="s1">AWS Partition: {{partition_name}}</span></p>
<p class="p1"><span class="s1">AWS Account ID: {{account_id}}</span></p>
<p class="p1"><span class="s1">AWS Account Name: {{account_name}}</span></p>
<p class="p1"><span class="s1">Time of Detection: {{timestamp}}</span></p>
<p class="p1"><span class="s1">Action: <br>{{actions}}</span></p>
<p class="p1"><span class="s1">Rotation Period: {{rotation_period}}</span></p>
<p class="p1"><span class="s1">Installation Grace Period: {{installation_grace_period}}</span></p>
<p class="p1"><span class="s1">Recovery Grace Period: {{recovery_grace_period}}</span></p>
<p class="p1"><span class="s1">------------------------------------------------------<br>
<p class="p1"><span class="s1"><br>
Need help reviewing your IAM Key usage? Check out this guide: <a href="https://wiki.example.com/iam-key-rotation">How to Identify IAM Key Usage</a>.<br>
<br>
Got questions? Reach out to {{sender_email}} or open a support ticket at https://support.example.com.<br>
<br>
Thanks,<br>
<br>
Cloud Platform Team</span></p>
</body>
</html>''',
    'iam-auto-key-rotation-enforcement.html': '''<!DOCTYPE html PUBLIC "-//W3C//DTD HTML 4.01//EN" "http://www.w3.org/TR/html4/strict.dtd">
<html>
<head>
  <meta http-equiv="Content-Type" content="text/html; charset=utf-8">
  <meta http-equiv="Content-Style-Type" content="text/css">
  <title></title>
  <style type="text/css">
    p.p1 {margin: 0.0px 0.0px 0.0px 0.0px; font: 12.0px Helvetica; color: #000000; -webkit-text-stroke: #000000}
    p.p2 {margin: 0.0px 0.0px 0.0px 0.0px; font: 12.0px Helvetica; color: #000000; -webkit-text-stroke: #000000; min-height: 14.0px}
    span.s1 {font-kerning: none}
  </style>
</head>
<body>
<p class="p1"><span class="s1">Hello,<br>
<br>
Keeping things secure is super important to us at Your Company. To make sure we're staying on top of security best practices, we're rolling out an automatic 90-day warning and rotation system for AWS IAM User Access Keys.<br>
<br>
Why does this matter to you?<br>
Rotating IAM credentials regularly helps prevent unauthorized access if a key ever gets compromised. This simple step can make a huge difference in securing your AWS resources.<br>
<br>
What's changing?<br>
The system will automatically rotate non-compliant keys. This means you'll need to update your applications with new Access Key pairs every 90 days. These keys will be stored in AWS Secrets Manager, with access restricted to your application's IAM User. After rotation, you'll have a 10-day grace period before old Access Keys are disabled, followed by another 10 days before deletion. During this time, you can still use old keys to retrieve new ones from Secrets Manager.<br>
<br>
By enabling this, you align with compliance standards such as SOC2, the Center of Internet Security AWS Foundations Benchmark, APRA, MAS, NIST, and the AWS Well-Architected Framework.
</span></p>

<br>
<p class="p1"><span class="s1">IAM Access Key in Violation:</span><br>
<p class="p1"><span class="s1">------------------------------------------------------<br>
<p class="p1"><span class="s1">AWS Partition: {{partition_name}}</span></p>
<p class="p1"><span class="s1">AWS Account ID: {{account_id}}</span></p>
<p class="p1"><span class="s1">AWS Account Name: {{account_name}}</span></p>
<p class="p1"><span class="s1">Time of Detection: {{timestamp}}</span></p>
<p class="p1"><span class="s1">Action: <br>{{actions}}</span></p>
<p class="p1"><span class="s1">Rotation Period: {{rotation_period}}</span></p>
<p class="p1"><span class="s1">Installation Grace Period: {{installation_grace_period}}</span></p>
<p class="p1"><span class="s1">Recovery Grace Period: {{recovery_grace_period}}</span></p>
<p class="p1"><span class="s1">------------------------------------------------------<br>
<p class="p1"><span class="s1"><br>
Need help figuring out where your IAM Key is being used and how to rotate it? Check out this guide: <a href="https://wiki.example.com/iam-key-rotation">How to Identify and Rotate IAM Keys</a>.<br>
<br>
Got questions? Reach out to {{sender_email}} or open a support ticket at https://support.example.com.<br>
<br>
Thanks,<br>
<br>
Cloud Platform Team</span></p>
</body>
</html>'''
}


class Notifier:
    def __init__(self, sender_email: str, recipient_email: str,
                 email_template: str, subject: str) -> None:
        self.sender_email = sender_email
        self.recipient_email = recipient_email
        self.email_template = email_template
        self.subject = subject

    @staticmethod
    def __parse_arn(arn):
        # http://docs.aws.amazon.com/general/latest/gr/aws-arns-and-namespaces.html
        elements = arn.split(':', 5)
        result = {
            'arn': elements[0],
            'partition': elements[1],
            'service': elements[2],
            'region': elements[3],
            'account': elements[4],
            'resource': elements[5],
            'resource_type': None
        }
        if '/' in result['resource']:
            result['resource_type'], result['resource'] = \
                result['resource'].split('/', 1)  # NOQA
        elif ':' in result['resource']:
            result['resource_type'], result['resource'] = \
                result['resource'].split(':', 1)  # NOQA
        return result

    def __get_template(self, template_name):
        log.info(f'Getting embedded template: {template_name}')

        if template_name not in EMAIL_TEMPLATES:
            error_msg = f'Template {template_name} not found. Available templates: {list(EMAIL_TEMPLATES.keys())}'
            log.error(error_msg)
            raise ValueError(error_msg)

        template = EMAIL_TEMPLATES[template_name]
        log.info(f'Successfully retrieved embedded template: {template_name}')
        return template

    def __render_email_body(self, template_values: dict):
        subject = self.subject
        # get the appropriate S3 Key for the template
        template_s3_key = self.email_template
        if not template_s3_key:
            log.error(f'Unable to get template for {subject}')
            raise ValueError(f'Unable to get template for {subject}')
        else:
            # stream the template contents from S3
            email = self.__get_template(template_s3_key)

            log.info('Rendering email contents')
            for k, v in template_values.items():
                placeholder = '{{' + f'{k}' + '}}'
                if isinstance(v, list):
                    value = self.__format_html_list(v)
                else:
                    value = str(v)
                email = email.replace(placeholder, value)

            log.info(f'Rendered Email: {email}')

            return email

    @staticmethod
    def __format_html_list(value):
        value_formatted = ''
        for line in value:
            value_formatted += f'&bull; {str(line)}<br>'
        return value_formatted

    def send_email(self, template_values):
        ses = boto3.client('ses')

        email_body = self.__render_email_body(template_values)

        try:
            log.info(f'Sending email to {self.recipient_email}')
            resp = ses.send_email(
                Source=self.sender_email,
                Destination={
                    'ToAddresses': [
                        self.recipient_email,
                    ]
                },
                Message={
                    'Subject': {
                        'Data': self.subject
                    },
                    'Body': {
                        'Text': {
                            'Data': email_body
                        },
                        'Html': {
                            'Data': email_body
                        }
                    }
                }
            )
            log.info('Email sent successfully - Exiting Gracefully')
            return resp
        except ClientError as err:
            log.error(
                f'Encountered error while attempting to send email - {err}'
            )
            raise err
