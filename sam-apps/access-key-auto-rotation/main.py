# (c) 2021 Amazon Web Services, Inc. or its affiliates. All Rights Reserved.
# This AWS Content
# is provided subject to the terms of the AWS Customer Agreement available at
# https://aws.amazon.com/agreement/ or other written agreement between Customer
# and Amazon Web Services, Inc.


import time

from config import Config, log
from sts_connection_handler import get_account_session
from force_rotation_handler import check_force_rotate_users
from account_scan import get_actions_for_account
from notification_handler import send_to_notifier
from key_actions import log_actions, execute_actions

timestamp = int(round(time.time() * 1000))

config = Config()


def lambda_handler(event, context):
    """Handler for Lambda.

    :param event: Dictionary account object (Account ID and Email) sent to Lambda via 'Account Inventory' Lambda Function
    :param context: Lambda context object
    """

    log.info('Function starting.')

    # Error handling - Ensure that the correct object is getting passed
    # to the function
    if "account" not in event and "email" not in event and "name" not in event:
        log.error(
            'The JSON Event Message getting passed to this Lambda Function'
            ' is malformed. Please ensure it has "account", "name" and "email" as'
            ' part of the JSON body.')

    # check for users to be force rotated via test event
    force_rotate_users = check_force_rotate_users(event)

    # check for dryrun flag
    dryrun = str(event.get('dryrun')).lower() == 'true' or config.dryrun

    # Parse event to get Account ID and Email
    aws_account_id = event['account']
    account_name = event['name']
    account_email = event['email']
    tags = event.get('tags', {})  # Get 'tags' dictionary if available

    # Only check 'tags' if dryrun is initially False 
    if not dryrun:
        # Check 'tags' for iamRotationPolicy
        if tags.get('iamRotationPolicy') == 'Strict':  
            log.info("Tag iamRotationPolicy is 'Strict' - Overriding dryrun to False.")
            dryrun = False
        else:
            log.info("Tag iamRotationPolicy is not 'Strict' - Overriding dryrun to True.")
            dryrun = True

    log.info(f'Dryrun is set to: {dryrun}')
    log.info(f'Currently evaluating Account ID: {aws_account_id} | Account Name: {account_name}')

    account_session = get_account_session(aws_account_id)
    action_queue = get_actions_for_account(account_session, force_rotate_users)

    if action_queue:
        log_actions(action_queue, dryrun)
        if dryrun:
            send_to_notifier(context, aws_account_id, account_name, account_email,
                             action_queue, dryrun, config.emailTemplateAudit)
        else:
            execute_actions(action_queue, account_session)
            send_to_notifier(context, aws_account_id, account_name, account_email,
                             action_queue, dryrun, config.emailTemplateEnforce)

    log.info('---------------------------')
    log.info('Function has completed.')