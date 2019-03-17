from troposphere import Ref, Join, Split, Select
from troposphere.elasticloadbalancingv2 import (
    LoadBalancer, LoadBalancerAttributes, TargetGroup, Listener, ListenerRule, Action, Condition,
    Matcher, Certificate
)
from troposphere.cloudwatch import Alarm, MetricDimension


# make target groups for the 3 tiers
def make_target_groups(t):
    def tg(name):
        return t.add_resource(TargetGroup(
            name,
            Port="80",
            Protocol="HTTP",
            VpcId=Ref('VPC'),
            HealthCheckPath=Ref("HealthcheckPath"),
            HealthCheckIntervalSeconds=30,
            HealthCheckProtocol="HTTP",
            HealthCheckTimeoutSeconds=5,
            HealthyThresholdCount=5,
            UnhealthyThresholdCount=2,
            Matcher=Matcher(HttpCode="200"),
            Tags=[
                {'Key': 'lh-app', 'Value': Ref('lhAppTag')},
                {'Key': 'lh-app-env', 'Value': Ref('lhAppEnvTag')}
            ]
        ))

    return {'spa': tg('spaTG'), 'api': tg('apiTG'), 'admin': tg('adminTG')}


# Create a load balancer with HTTP and HTTPS listeners and target groups for SPA, API and admin instances.
# Each listener has rules for API and admin requests and a default for SPA requests.
# The HTTPS listener is configured with an existing cert.
def make_load_balancer(t, security_groups, target_groups):
    alb = t.add_resource(LoadBalancer(
        "alb",
        Scheme="internet-facing",
        Subnets=[Ref('Subnet1'), Ref('Subnet2'), Ref('Subnet3')],
        SecurityGroups=[i.Ref() for i in security_groups],
        LoadBalancerAttributes=[
            LoadBalancerAttributes(
                Key='access_logs.s3.enabled',
                Value=Ref('ALBAccessLogsEnabled')
            ),
            LoadBalancerAttributes(
                Key='access_logs.s3.bucket',
                Value=Ref('ALBAccessLogsBucket')
            )
        ],
        DependsOn=[i.title for i in security_groups],
        Tags=[
            {'Key': 'lh-app', 'Value': Ref('lhAppTag')},
            {'Key': 'lh-app-env', 'Value': Ref('lhAppEnvTag')}
        ]
    ))

    http_listener = t.add_resource(Listener(
        "httpListener",
        Port="80",
        Protocol="HTTP",
        LoadBalancerArn=Ref(alb),
        DefaultActions=[Action(
            Type="forward",
            TargetGroupArn=Ref(target_groups['spa'])
        )]
    ))

    t.add_resource(ListenerRule(
        "httpListenerRuleApi",
        ListenerArn=Ref(http_listener),
        Conditions=[Condition(
            Field="host-header",
            Values=[Join('-', ['api', Ref('AppDomain')])]
        )],
        Actions=[Action(
            Type="forward",
            TargetGroupArn=Ref(target_groups['api'])
        )],
        Priority="1"
    ))

    t.add_resource(ListenerRule(
        "httpListenerRuleAdmin",
        ListenerArn=Ref(http_listener),
        Conditions=[Condition(
            Field="host-header",
            Values=[Join('-', ['admin', Ref('AppDomain')])]
        )],
        Actions=[Action(
            Type="forward",
            TargetGroupArn=Ref(target_groups['admin'])
        )],
        Priority="2"
    ))

    https_listener = t.add_resource(Listener(
        'httpsListener',
        Port="443",
        Protocol="HTTPS",
        LoadBalancerArn=Ref(alb),
        DefaultActions=[Action(
            Type="forward",
            TargetGroupArn=Ref(target_groups['spa'])
        )],
        Certificates=[Certificate("certificate", CertificateArn=Ref('SSLCertArn'))]
    ))

    t.add_resource(ListenerRule(
        "httpsListenerRuleApi",
        ListenerArn=Ref(https_listener),
        Conditions=[Condition(
            Field="host-header",
            Values=[Join('-', ['api', Ref('AppDomain')])]
        )],
        Actions=[Action(
            Type="forward",
            TargetGroupArn=Ref(target_groups['api'])
        )],
        Priority="1"
    ))

    t.add_resource(ListenerRule(
        "httpsListenerRuleAdmin",
        ListenerArn=Ref(https_listener),
        Conditions=[Condition(
            Field="host-header",
            Values=[Join('-', ['admin', Ref('AppDomain')])]
        )],
        Actions=[Action(
            Type="forward",
            TargetGroupArn=Ref(target_groups['admin'])
        )],
        Priority="2"
    ))

    return alb


def make_load_balancer_alarms(t, alb, target_groups):
    for tier, tg in target_groups.items():
        t.add_resource(Alarm(
            tier + 'TargetResponseTimeAlarm',
            AlarmDescription='Alarm if a target takes too long to respond to an HTTP request',
            Namespace='AWS/ApplicationELB',
            MetricName='TargetResponseTime',
            Dimensions=[
                # See the following for doc on the structure of the metric dimensions:
                # https://docs.aws.amazon.com/AmazonCloudWatch/latest/monitoring/elb-metricscollected.html#load-balancer-metric-dimensions-alb
                # So for we have to get the ARN and use Split and Select to grab the right bit.
                # We split on the delimeter ':' and grab the last element (index 5). For the TG this is fine.
                # For the ALB, however, we need to additionally trim the prefix "loadbalancer/". I do that by splitting
                # again on the prefix 'loadbalancer/' and selecting index 1 from the result (index 0 is empty).
                MetricDimension(
                    Name='LoadBalancer',
                    Value=Select(1, Split('loadbalancer/', Select(5, Split(':', Ref(alb)))))
                ),
                MetricDimension(
                    Name='TargetGroup',
                    Value=Select(5, Split(':', Ref(tg)))
                )
            ],
            Statistic='Average',
            Period='60',
            EvaluationPeriods='1',
            Threshold=Ref('TargetResponseTimeAlarmThreshold'),
            ComparisonOperator='GreaterThanThreshold',
            AlarmActions=[Ref('NotificationTopicARN')]
        ))
