# (c) 2021 Amazon Web Services, Inc. or its affiliates. All Rights Reserved.
# This AWS Content is provided subject to the terms of the AWS Customer Agreement available at
# https://aws.amazon.com/agreement/ or other written agreement between Customer
# and Amazon Web Services, Inc.

"""Account Inventory Handler.

This module provides the functionality to dynamically query AWS Organizations
for a full list of account IDs and emails. This script kicks off the
access_key_auto_rotation function.
"""

import boto3
import os
import json
import logging
import time
from datetime import datetime


# setup script logging
log = logging.getLogger(__name__)
log.setLevel(logging.INFO)

# AWS Organizations Client
org_client = boto3.client('organizations')

# AWS Lambda Client
lambda_client = boto3.client('lambda')

# main Python Function, parses events sent to lambda
def lambda_handler(event, context):
    # environment Variables
    lambdaRotationFunction = os.environ['LambdaRotationFunction']
    ou_id = os.getenv('InventoryOU')
   
    # get AWS account details from AWS Organizations
    if ou_id:
        account_list = list_aws_accounts_for_ou(ou_id)
    else:
        account_list = list_all_aws_accounts()
   
    # loop through all accounts and trigger the IAM Rotation Lambda
    run_lambda_function(account_list, lambdaRotationFunction)


def list_all_aws_accounts():
    """
    Gets the current list of all AWS Accounts from AWS Organizations.

    :return The current dict of all AWS Accounts.
    """
    account_list = []
    try:
        # max limit of 20 users per listing
        # use paginator to iterate through each page
        paginator = org_client.get_paginator('list_accounts')
        page_iterator = paginator.paginate()
        for page in page_iterator:
            for acct in page['Accounts']:
                account_list.append(acct)
    except org_client.exceptions.ClientError as error:
        log.error(f'Error: {error}')
   
    return account_list


def list_aws_accounts_for_ou(ou_id):
    """
    Gets the current list of AWS Accounts in an OU from AWS Organizations.

    :return The current dict of all AWS Accounts.
    """
    log.info(f"Searching for accounts in OU {ou_id}")
    account_list = []

    # first add accounts directly in the ou
    try:
        # max limit of 20 accounts per listing
        # use paginator to iterate through each page
        lafp_paginator = org_client.get_paginator('list_accounts_for_parent')
        lafp_page_iterator = lafp_paginator.paginate(ParentId=ou_id)
        for page in lafp_page_iterator:
            for acct in page['Accounts']:
                account_list.append(acct)
    except org_client.exceptions.ClientError as error:
        log.error(f'Error: {error}')

    # next add accounts in child ous
    try:
        # max limit of 20 children per listing
        # use paginator to iterate through each page
        lc_paginator = org_client.get_paginator('list_children')
        ou_page_iterator = lc_paginator.paginate(
            ParentId=ou_id,
            ChildType='ORGANIZATIONAL_UNIT'
        )
        for page in ou_page_iterator:
            for child in page['Children']:
                # recurse over child ous and add the accounts they contain
                log.info(f"Adding accounts from child OU {child['Id']}")
                account_list += list_aws_accounts_for_ou(child['Id'])
    except org_client.exceptions.ClientError as error:
        log.error(f'Error: {error}')

    log.info(f"Found {len(account_list)} accounts in OU {ou_id}")
    return account_list


def get_account_tags(account_id):
    """
    Retrieves AWS account tags.

    :param account_id: AWS account ID.
    :return: Dictionary of account tags.
    """
    try:
        response = org_client.list_tags_for_resource(ResourceId=account_id)
        tags = {tag['Key']: tag['Value'] for tag in response.get('Tags', [])}
        return tags
    except org_client.exceptions.ClientError as error:
        log.error(f'Error retrieving tags for account {account_id}: {error}')
        return {}


def run_lambda_function(awsAccountArray, lambdaFunction):
    """
    Invokes the Lambda Function that evaluates key rotation.
    Implements rate limiting to prevent API throttling.

    :return Response from Invoke command.
    """
    # Rate limiting: max 20 accounts per minute (conservative for API safety)
    MAX_ACCOUNTS_PER_MINUTE = 20

    invoked_count = 0
    window_start = datetime.now()
    response = None

    for account in awsAccountArray:
        # skip accounts that are suspended
        if account['Status'] != 'ACTIVE':
            continue

        # Rate limiting check
        invoked_count += 1
        if invoked_count > MAX_ACCOUNTS_PER_MINUTE:
            elapsed_seconds = (datetime.now() - window_start).total_seconds()
            if elapsed_seconds < 60:
                sleep_time = 60 - elapsed_seconds
                log.info(
                    f'Rate limit reached ({invoked_count} accounts). '
                    f'Waiting {sleep_time:.1f}s before continuing...'
                )
                time.sleep(sleep_time)

            # Reset counter and window
            window_start = datetime.now()
            invoked_count = 1

        account_tags = get_account_tags(account['Id'])

        jsonPayload = {
            "account": account['Id'],
            "name": account['Name'],
            "email": account['Email'],
            "tags": account_tags
        }

        lambdaPayloadEncoded = json.dumps(jsonPayload).encode('utf-8')
        try:
            response = lambda_client.invoke(
                FunctionName=lambdaFunction, InvocationType='Event',
                Payload=lambdaPayloadEncoded)

            lambdaPayloadEncoded_str = str(lambdaPayloadEncoded)
            log.info(f'Invoked: FunctionName={lambdaFunction},'
                     f' InvocationType=Event,'
                     f' Account={account["Id"]}')
        except lambda_client.exceptions.ClientError as error:
            log.error(f'Error invoking Lambda for account {account["Id"]}: {error}')

    log.info(f'Successfully invoked Lambda for {invoked_count} accounts')
    return response
