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
import warnings
import requests


warnings.filterwarnings("ignore")
logger = logging.getLogger()
logger.setLevel(logging.INFO)

timestamp_format = '%Y-%m-%dT%H:%M:%SZ'
now = datetime.datetime.now()
now = now.strftime(timestamp_format)

# Create InfluxDB Client
client = InfluxDBClient(host="influxdb000.management.skyfall.io", port=8086, username='sysops', password='g0th@m', database="pdpsysops", ssl=True, verify_ssl=False)
# Create Smoke Test Measurement Lists
hdfs_status = []
mapreduce2_status = []
zookeeper_status = []


# Slack Alert Channels
management_channel_web_hook_url = 'https://hooks.slack.com/services/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'

# Entry Point
def lambda_handler(event, context):
    timestamp = event['time'] if 'time' in event else now
    item = None
    dynamo_db1 = boto3.resource('dynamodb')
    last_smt_id="BLANK"

    # Write Data To DynamoDB SmokeTestsTable
    table1 = dynamo_db1.Table('SmokeTestsTable')
    decoded_record_data = [base64.b64decode(record['kinesis']['data']) for record in event['Records']]
    #for decoded_record in decoded_record_data:
    #    print(json.loads(decoded_record))
    deserialized_data = [json.loads(decoded_record) for decoded_record in decoded_record_data]
    with table1.batch_writer() as batch_writer:
        for item in deserialized_data:
            node_env = item['node_env']
            smt_id = item['smt_id']
            node_name = item['node_name']
            smt_name = item['smt_name']
            measurement = smt_name + '_status'
            smt_component = item['smt_component']
            run_status = item['run_status']
            last_run = item['last_run']
            goss_data = item['goss_data']
            send_alert = False
            probe_successful = True

            # Check if duplicate
            if last_smt_id == smt_id:
                continue
            else:
                last_smt_id = smt_id

            # Check Status
            if run_status == "FAILED":
                send_alert = True
                probe_successful = False

            # Add DataPoint To Appropriate Measurement
            if smt_name == "hdfs":
                hdfs_status.append({"measurement":"hdfs_status","tags":{"environment":node_env,"component":smt_component,"node":node_name,"smt_id":smt_id}, "time":last_run, "fields":{"probe_successful":probe_successful}})
            elif smt_name == "mapreduce2":
                mapreduce2_status.append({"measurement":"mapreduce2_status","tags":{"environment":node_env,"component":smt_component,"node":node_name,"smt_id":smt_id}, "time":last_run, "fields":{"probe_successful":probe_successful}})
            elif smt_name == "zookeeper":
                zookeeper_status.append({"measurement":"zookeeper_status","tags":{"environment":node_env,"component":smt_component,"node":node_name,"smt_id":smt_id}, "time":last_run, "fields":{"probe_successful":probe_successful}})

            # Log Output To Cloudwatch
            log = f'{timestamp} {{"node_env": "{node_env}", "smt_id": "{smt_id}", "node_name": "{node_name}", "smt_name": "{smt_name}", "smt_component": "{smt_component}", "run_status": "{run_status}", "alert_sent": {send_alert}, "last_run": "{last_run}"}}'
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
                    'SmokeTestComponent': smt_component,
                    'SmokeTestStatus': run_status,
                    'LastRun': last_run,
                    'GossData': {
                        'results': result_set
                    }
                }
            )

            # Send Alert On Failure
            if send_alert:
                # CHECK IF THIS ALERT HAS BEEN SENT ALREADY
                last_probe_successful=False
                query_where = 'select probe_successful from '+measurement+' where node=$node and component=$component order by time desc limit 1;'
                bind_params = {'component': smt_component, 'node': node_name}
                rs = client.query(query_where, bind_params=bind_params)
                points = rs.get_points()
                for point in points:
                    last_probe_successful = point['probe_successful']

                if last_probe_successful:
                    if node_env == "management":
                        # SEND ALERT VIA SLACK
                        slack_msg = {'username': 'webhookbot', 'icon_emoji': ':ghost:', 'text': 'VALIDATION TEST FAILURE: \n[node] ' + node_name + ' <http://ambari000.management.skyfall.io:8080/#/main/hosts/'+node_name+'/summary| VIEW IN AMBARI> \n[service] ' + smt_name + ' \n[component] ' + smt_component + ' \n[smt_id] ' + smt_id}
                        requests.post(management_channel_web_hook_url,data=json.dumps(slack_msg))
                        # SEND ALERT TO CLOUDWATCH
                        alert_log = f'{timestamp} {{"alert_msg": "alert sent", "node_name": "{node_name}", "smt_id": "{smt_id}", "smt_name": "{smt_name}", "smt_component":"{smt_component}"}}'
                        print(alert_log)

            # Write Data To InfluxDB
            client.write_points(hdfs_status)
            client.write_points(mapreduce2_status)
            client.write_points(zookeeper_status)

    # CleanUp
    client.close()
