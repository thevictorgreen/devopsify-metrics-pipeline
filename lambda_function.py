import base64
import boto3
import datetime
import decimal
import influxdb
from influxdb import InfluxDBClient
from influxdb import SeriesHelper
import json
import logging
import os
import time


logger = logging.getLogger()
logger.setLevel(logging.INFO)

timestamp_format = '%Y-%m-%dT%H:%M:%SZ'
now = datetime.datetime.now()
now = now.strftime(timestamp_format)

def lambda_handler(event, context):
    timestamp = event['time'] if 'time' in event else now

    item = None
    dynamo_db1 = boto3.resource('dynamodb')

    # Write Data To SmokeTestsTable
    table1 = dynamo_db1.Table('SmokeTestsTable')
    decoded_record_data = [base64.b64decode(record['kinesis']['data']) for record in event['Records']]
    deserialized_data = [json.loads(decoded_record) for decoded_record in decoded_record_data]
    with table1.batch_writer() as batch_writer:
        for item in deserialized_data:
            node_env = item['node_env']
            smt_id = item['smt_id']
            node_name = item['node_name']
            smt_name = item['smt_name']
            run_status = item['run_status']
            last_run = item['last_run']
            goss_data = item['goss_data']
            send_alert = False

            # Check Status
            if run_status == "FAILED":
                send_alert = True

            # Send Alert On Failure
            if send_alert:
                alert_log = f'{timestamp} {{"alert_msg": "alert sent", "node_name": "{node_name}", "smt_id": "{smt_id}", "smt_name": "{smt_name}"}}'
                print(alert_log)

            # Log Output To Cloudwatch
            log = f'{timestamp} {{"node_env": "{node_env}", "smt_id": "{smt_id}", "node_name": "{node_name}", "smt_name": "{smt_name}", "run_status": "{run_status}", "alert_sent": {send_alert}, "last_run": "{last_run}"}}'
            print(log)

            # Build ResultSet for SmokeTest Details
            result_set = []
            for std_item in goss_data['results']:
                result_set.append({"property": std_item['property'], "resource-id": std_item['resource-id'], "resource-type": std_item['resource-type'], "successful": std_item['successful'], "summary-line": std_item['summary-line']})

            # Write All Items SmokeTestsTable
            batch_writer.put_item(
                Item = {
                    'Environment': node_env,
                    'SmokeTestID': smt_id,
                    'NodeName': node_name,
                    'SmokeTestName': smt_name,
                    'SmokeTestStatus': run_status,
                    'LastRun': last_run,
                    'GossData': {
                        'results': result_set
                    }
                }
            )
