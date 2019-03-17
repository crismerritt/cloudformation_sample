# Written for Python 3

# This is a CloudFormation template for the load-balancer/autoscaling/EC2 cluster that runs the LifeHouse
# "referral application". See also the 'ami' directory (sibling to the dir containing this file) for the code
# that creates the AMIs used here. We are using the Python troposphere library, which generates the CloudFormation
# JSON template.

from troposphere import Template, Parameter, Ref, Equals
from security_groups import make_security_groups
from load_balancer import make_load_balancer, make_target_groups, make_load_balancer_alarms
from autoscaling_group import make_launch_configuration, make_autoscaling_group
from iam import make_instance_profile
from utils import tag_name_to_param_name

# tweak ALL-CAPS settings here:
APP_NAME = 'refapp'
DEFAULT_DOMAIN = 'test-friends.life-house.com'
DEFAULT_VPC = 'vpc-93d88cfa'  # default us-east-2 VPC in LifeHouse account
SUBNET_1 = 'subnet-12ae8a7b'  # default public subnet in us-east-2a in Lifehouse account
SUBNET_2 = 'subnet-3626474d'  # default public subnet in us-east-2b in Lifehouse account
SUBNET_3 = 'subnet-51278e1c'  # default public subnet in us-east-2c in Lifehouse account
SPA_AMI_USEAST2 = 'ami-a3bf8cc6'
API_AMI_USEAST2 = 'ami-192b187c'
ADMIN_AMI_USEAST2 = SPA_AMI_USEAST2  # use the SPA AMI for admin
DEFAULT_NOTIFICATION_TOPIC_ARN = 'arn:aws:sns:us-east-2:306976287633:lifehouse-techops-events'
DEFAULT_CERT = 'arn:aws:iam::306976287633:server-certificate/lifehousewildcard'
DEFAULT_LOGS_BUCKET = 'life-house-logs'
DEFAULT_DB_SG = 'sg-0ce0a567'
HEALTHCHECK_PATH = '/healthcheck'
KEY_NAMES = [APP_NAME + '-dev-keypair', APP_NAME + '-staging-keypair', APP_NAME + '-prod-keypair', ]
DEFAULT_TARGET_RESPONSE_TIME_ALARM_THRESHOLD = 0.2

SPA_ASG_TAGS = {
    'env-file': ['.env.dev', '.env.staging', '.env.prod'],
    'repo-branch': 'master',
    'repo-url': 'refapp-spa.github.com:Life-House/referral-spa.git',
    'autoredeploy': ['false', 'true']
}

API_ASG_TAGS = {
    'env-file': ['.env.dev', '.env.staging', '.env.prod'],
    'repo-branch': 'master',
    'repo-url': 'git@github.com:Life-House/referral-api.git',
    'autoredeploy': ['false', 'true']
}

ADMIN_ASG_TAGS = {
    'env-file': ['.env.dev', '.env.staging', '.env.prod'],
    'repo-branch': 'master',
    'repo-url': 'refapp-admin.github.com:Life-House/referral-admin-spa.git',
    'autoredeploy': ['false', 'true']
}


def add_parameters(t):
    t.add_parameter(Parameter(
        "AppDomain",
        Type="String",
        Description="DNS domain of app",
        Default=DEFAULT_DOMAIN,
    ))

    t.add_parameter(Parameter(
        "VPC",
        Type="String",
        Description="Existing VPC to deploy into",
        Default=DEFAULT_VPC,
    ))

    t.add_parameter(Parameter(
        "Subnet1",
        Type="String",
        Description="An existing public subnet in the VPC",
        Default=SUBNET_1,
    ))

    t.add_parameter(Parameter(
        "Subnet2",
        Type="String",
        Description="Another existing public subnet in the VPC",
        Default=SUBNET_2,
    ))

    t.add_parameter(Parameter(
        "Subnet3",
        Type="String",
        Description="Yet another existing public subnet in the VPC",
        Default=SUBNET_3,
    ))

    t.add_parameter(Parameter(
        "spaAMI",
        Type="String",
        Description="AMI to use for the SPA tier",
        Default=SPA_AMI_USEAST2,
    ))

    t.add_parameter(Parameter(
        "apiAMI",
        Type="String",
        Description="AMI to use for the API tier",
        Default=API_AMI_USEAST2,
    ))

    t.add_parameter(Parameter(
        "adminAMI",
        Type="String",
        Description="AMI to use for the Admin tier",
        Default=ADMIN_AMI_USEAST2,
    ))

    t.add_parameter(Parameter(
        "DatabaseSG",
        Type="String",
        Description="Existing security group to add API instances to so they can access the DB",
        Default=DEFAULT_DB_SG,
    ))

    t.add_parameter(Parameter(
        "InstanceType",
        Type="String",
        Description="EC2 instance type - t2.medium for dev/staging, c5.large for prod",
        Default="t2.medium",
        AllowedValues=["t2.medium", "c5.large"]
    ))

    t.add_parameter(Parameter(
        "DetailedInstanceMonitoring",
        Type="String",
        Description="Enable detailed instance monitoring when set to True (prod: True)",
        Default="False",
        AllowedValues=["True", "False"]
    ))

    t.add_parameter(Parameter(
        "ALBAccessLogsEnabled",
        Type="String",
        Description="Enable access logging on the load balancer when set to true (prod: true)",
        Default="false",
        AllowedValues=["true", "false"]
    ))

    t.add_parameter(Parameter(
        "ALBAccessLogsBucket",
        Type="String",
        Description="S3 bucket for access logs",
        Default=DEFAULT_LOGS_BUCKET
    ))

    t.add_parameter(Parameter(
        "TargetResponseTimeAlarmThreshold",
        Type="Number",
        Description="Threshold for response time alarm (in seconds - ex: 0.1 == 100 milliseconds)",
        Default=DEFAULT_TARGET_RESPONSE_TIME_ALARM_THRESHOLD
    ))

    t.add_parameter(Parameter(
        "KeyName",
        Type="String",
        Description="Name of the SSH keypair for accessing EC2 instances",
        AllowedValues=KEY_NAMES,
        Default=KEY_NAMES[0]
    ))

    t.add_parameter(Parameter(
        "SSLCertArn",
        Type="String",
        Default=DEFAULT_CERT,
        Description="ARN of the SSL cert to use for the public SSL connection to the load balancer"
    ))

    t.add_parameter(Parameter(
        "HealthcheckPath",
        Type="String",
        Default=HEALTHCHECK_PATH,
        Description="Path for load balancer to check health of EC2 instances"
    ))

    t.add_parameter(Parameter(
        "spaHealthcheckGracePeriod",
        Type="Number",
        Default=300,
        Description="How long the ASG waits to start health-checking SPA instances after launching an instance"
    ))

    t.add_parameter(Parameter(
        "apiHealthcheckGracePeriod",
        Type="Number",
        Default=300,
        Description="How long the ASG waits to start health-checking API instances after launching an instance"
    ))

    t.add_parameter(Parameter(
        "adminHealthcheckGracePeriod",
        Type="Number",
        Default=300,
        Description="How long the ASG waits to start health-checking the Admin instances after launching an instance"
    ))

    t.add_parameter(Parameter(
        "spaInitialASGSize",
        Type="Number",
        Default=1,
        Description="Initial size of the SPA autoscaling group before target tracking scaling (prod: 3)"
    ))

    t.add_parameter(Parameter(
        "spaMinASGSize",
        Type="Number",
        Default=1,
        Description="Minimum size of the SPA autoscaling group (prod: 3)"
    ))

    t.add_parameter(Parameter(
        "spaMaxASGSize",
        Type="Number",
        Default=1,
        Description="Maximum size of the SPA autoscaling group (prod: 6)"
    ))

    t.add_parameter(Parameter(
        "apiInitialASGSize",
        Type="Number",
        Default=1,
        Description="Initial size of the API autoscaling group before target tracking scaling (prod: 3)"
    ))

    t.add_parameter(Parameter(
        "apiMinASGSize",
        Type="Number",
        Default=1,
        Description="Minimum size of the API autoscaling group (prod: 3)"
    ))

    t.add_parameter(Parameter(
        "apiMaxASGSize",
        Type="Number",
        Default=1,
        Description="Maximum size of the API autoscaling group (prod: 6)"
    ))

    t.add_parameter(Parameter(
        "adminInitialASGSize",
        Type="Number",
        Default=1,
        Description="Initial size of the Admin autoscaling group (doesn't scale)"
    ))

    t.add_parameter(Parameter(
        "adminMinASGSize",
        Type="Number",
        Default=1,
        Description="Minimum size of the Admin autoscaling group"
    ))

    t.add_parameter(Parameter(
        "adminMaxASGSize",
        Type="Number",
        Default=1,
        Description="Maximum size of the Admin autoscaling group"
    ))

    t.add_parameter(Parameter(
        'ASGEnableMetricsCollection',
        Type='String',
        Description='Enable ASG metrics collection (group size, etc) (prod: True)',
        Default='False',
        AllowedValues=['True', 'False']
    ))

    t.add_condition(
        'asg_enable_metrics_collection', Equals(Ref('ASGEnableMetricsCollection'), 'True')
    )

    t.add_parameter(Parameter(
        "NotificationTopicARN",
        Type="String",
        Default=DEFAULT_NOTIFICATION_TOPIC_ARN,
        Description="SNS topic to which to publish alarms and events"
    ))

    t.add_parameter(Parameter(
        "lhAppTag",
        Type="String",
        Description="lh-app tag for this cluster",
        Default="refapp"
    ))

    t.add_parameter(Parameter(
        'lhAppEnvTag',
        Type='String',
        Description='lh-app-env tag for this cluster',
        Default='test',
        AllowedValues=['test', 'dev', 'staging', 'prod']
    ))

    for tier, tags in {'spa': SPA_ASG_TAGS, 'api': API_ASG_TAGS, 'admin': ADMIN_ASG_TAGS}.items():
        for key in tags:
            v = tags[key]
            if isinstance(v, (list,)):
                t.add_parameter(Parameter(
                    tag_name_to_param_name(tier, key),
                    Type="String",
                    AllowedValues=v,
                    Default=v[0],  # first one in the list is the default
                    Description='Value of ' + key + ' tag for ' + tier + ' instances'
                ))
            else:
                t.add_parameter(Parameter(
                    tag_name_to_param_name(tier, key),
                    Type="String",
                    Default=v,
                    Description='Value of ' + key + ' tag for ' + tier + ' instances'
                ))


def main():
    t = Template()
    t.add_version("2010-09-09")
    t.add_description("Creates a LifeHouse app cluster")

    add_parameters(t)

    security_groups = make_security_groups(t)
    target_groups = make_target_groups(t)
    alb = make_load_balancer(t, [security_groups['alb']], target_groups)
    make_load_balancer_alarms(t, alb, target_groups)

    instance_profile = make_instance_profile(t)
    spa_user_data = open('user_data_spa.sh', 'r').read()
    api_user_data = open('user_data_api.sh', 'r').read()

    spa_lc = make_launch_configuration(t, 'spa', [security_groups['spa']], spa_user_data, instance_profile)

    # admin-lc uses the same user-data script and same AMI as SPA-lc
    admin_lc = make_launch_configuration(t, 'admin', [security_groups['admin']], spa_user_data, instance_profile)

    # API instances must also join the DB security group
    api_lc = make_launch_configuration(t, 'api', [security_groups['api'], 'DatabaseSG'], api_user_data,
                                       instance_profile)

    make_autoscaling_group(t, 'spa', spa_lc, target_groups['spa'], SPA_ASG_TAGS.keys())
    make_autoscaling_group(t, 'api', api_lc, target_groups['api'], API_ASG_TAGS.keys())
    make_autoscaling_group(t, 'admin', admin_lc, target_groups['admin'], ADMIN_ASG_TAGS.keys())

    print(t.to_json())


if __name__ == '__main__':
    main()
