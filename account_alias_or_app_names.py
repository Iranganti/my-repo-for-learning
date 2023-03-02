import argparse
import boto3
from boto3.dynamodb.conditions import Key

# python src\apis\test_dac\account_alias_or_app_names.py --environment alpha
# python src\apis\test_dac\account_alias_or_app_names.py --environment main

parser = argparse.ArgumentParser(description = 'test')

parser.add_argument(
	'--environment',
	help = 'Environment in which the data to be processed',
	type = str,
    required = True,
    choices=['alpha', 'main']
) 

parsed_args = parser.parse_args()

ENV = parsed_args.environment

iam_role = "hccp-cloud-admin"

if ENV == 'alpha':
    MASTER_ACCOUNT = '275348060467'
    table_name = 'account-manager-AccountsMetadataTableChildStack-DRXLJZWZKGZQ-AccountsMetadataTable-178AZWFAHMZH8'
else:
    MASTER_ACCOUNT = '768463683742'
    table_name = 'account-manager-AccountsMetadataTableChildStack-2BPJYUYSG3Q0-AccountsMetadataTable-10YX44OS90P3H'

admin_session = boto3.Session(profile_name=ENV)
admin_sts_client = admin_session.client('sts')

def assume_role(account_id):
    """Assume Role Function"""
    partition = admin_sts_client.get_caller_identity()['Arn'].split(":")[1]

    response = admin_sts_client.assume_role(
        RoleArn='arn:{}:iam::{}:role/{}'.format(
            partition,
            account_id,
            iam_role
        ),
        RoleSessionName='test'
    )
    return boto3.Session(
        aws_access_key_id=response['Credentials']['AccessKeyId'],
        aws_secret_access_key=response['Credentials']['SecretAccessKey'],
        aws_session_token=response['Credentials']['SessionToken']
    )

count = 0
inprogresscount = 0
master_session = assume_role(MASTER_ACCOUNT) 
actual_alias = ""
account_list = []
alias_list = []
org_client = master_session.client('organizations')

CONTINUE_SEARCH = True
NEXT_TOKEN = None

while CONTINUE_SEARCH:
    if not NEXT_TOKEN:
        response_accounts = org_client.list_accounts()
        accounts = response_accounts['Accounts']
        for i in accounts:
            account_list.append(i['Id'])
            count = count + 1
    else:
        response_accounts = org_client.list_accounts(NextToken=NEXT_TOKEN)
        accounts = response_accounts['Accounts']
        for i in accounts:        
            account_list.append(i['Id'])   
            count = count + 1     

    if 'NextToken' in response_accounts.keys():
        NEXT_TOKEN = response_accounts['NextToken']
    else:
        CONTINUE_SEARCH = False

print("Total number of accounts:", count)
print("\nIt takes a little while to start printing out the account alias detailed report.")

for i in account_list:
    inprogresscount = inprogresscount + 1
    member_session = assume_role(i)
    iam_client = member_session.client('iam')
    response = iam_client.list_account_aliases()
    if response['AccountAliases']:
        # print(i, " IAM Alias:", response['AccountAliases'][0])
        alias_list.append(i + " - " + response['AccountAliases'][0])
    # else:
        # print(i, " No IAM Alias")

dynamo_client = master_session.client('dynamodb')

response = dynamo_client.scan(
    TableName=table_name
)

print("\n\n")

print("{:<35} {:<12} {:<35} {:<45} {:<5} {:<12} {:<12} {:<45}".format("Application Name", "Account Id", "Account Owner", "Account Alias On Table", "VER", "Service", "ENV", "Actual IAM Alias"))
items = response['Items']
for item in items:
    if item['row-key']['S'] == 'CURRENT':
        if 'application' in item.keys():
            actual_alias = ""
            environment = ""
            if 'environment' in item.keys():
                environment = item['environment']['S']
            for z in alias_list:
                if item['id']['S'] in z:
                    actual_alias = z.strip()
                    actual_alias = actual_alias[15:]
            if 'iam-alias' in item.keys():
                print("{:<35} {:<12} {:<35} {:<45} {:<5} {:<12} {:<12} {:<45}".format(item['application']['S'], item['id']['S'], item['owner']['S'], item['iam-alias']['S'], item['account-version']['S'], item['service']['S'], environment, actual_alias))
            else:
                print("{:<35} {:<12} {:<35} {:<45} {:<5} {:<12} {:<12} {:<45}".format(item['application']['S'], item['id']['S'], item['owner']['S'], "", item['account-version']['S'], item['service']['S'], environment, actual_alias))
