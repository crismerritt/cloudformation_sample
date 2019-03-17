from troposphere import Ref, Base64, GetAZs, If
from troposphere.ec2 import BlockDeviceMapping, EBSBlockDevice
from troposphere.autoscaling import (
    LaunchConfiguration, AutoScalingGroup, NotificationConfigurations, Tag, MetricsCollection,
    ScalingPolicy, TargetTrackingConfiguration, PredefinedMetricSpecification,
    EC2_INSTANCE_LAUNCH, EC2_INSTANCE_LAUNCH_ERROR, EC2_INSTANCE_TERMINATE,
    EC2_INSTANCE_TERMINATE_ERROR
)
from utils import tag_name_to_param_name


def make_launch_configuration(t, tier, security_groups, user_data, instance_profile):
    lc = t.add_resource(LaunchConfiguration(
        tier + "LC",
        # ImageId=FindInMap(region_map_name, Ref("AWS::Region"), tier + "AMI"),
        ImageId=Ref(tier + 'AMI'),
        InstanceType=Ref('InstanceType'),
        InstanceMonitoring=Ref('DetailedInstanceMonitoring'),
        IamInstanceProfile=Ref(instance_profile),
        AssociatePublicIpAddress='True',
        SecurityGroups=list(map(lambda sg: Ref(sg), security_groups)),
        # SecurityGroups=[i.Ref() for i in security_groups],
        KeyName=Ref('KeyName'),
        BlockDeviceMappings=[
            BlockDeviceMapping(
                DeviceName='/dev/sda1',
                Ebs=EBSBlockDevice(
                    VolumeSize="8"
                ))
        ],
        UserData=Base64(user_data)
    ))

    return lc


# tier is one of 'spa', 'api', 'admin'
# tags is a list of the tag names for this asg, which must correspond to stack parameters
def make_autoscaling_group(t, tier, lc, target_group, tags):
    asg = t.add_resource(AutoScalingGroup(
        tier + "ASG",
        DesiredCapacity=Ref(tier + "InitialASGSize"),
        MinSize=Ref(tier + "MinASGSize"),
        MaxSize=Ref(tier + "MaxASGSize"),
        LaunchConfigurationName=Ref(lc),
        HealthCheckType="ELB",
        VPCZoneIdentifier=[Ref('Subnet1'), Ref('Subnet2'), Ref('Subnet3')],
        AvailabilityZones=GetAZs(Ref("AWS::Region")),
        TargetGroupARNs=[Ref(target_group)],
        HealthCheckGracePeriod=Ref(tier + "HealthcheckGracePeriod"),
        MetricsCollection=If('asg_enable_metrics_collection',
                             [MetricsCollection(Granularity='1Minute')],
                             Ref('AWS::NoValue')),
        NotificationConfigurations=[NotificationConfigurations(TopicARN=Ref("NotificationTopicARN"),
                                                               NotificationTypes=[EC2_INSTANCE_LAUNCH,
                                                                                  EC2_INSTANCE_LAUNCH_ERROR,
                                                                                  EC2_INSTANCE_TERMINATE,
                                                                                  EC2_INSTANCE_TERMINATE_ERROR])],

        # Explanation of the following: tags is an argument to this function which is a list of tag names that this
        # ASG will have. For example: [ 'env-file', 'repo-branch', 'repo-url' ]. Furthermore, we assume that for
        # each of these tag names there is a stack parameter called tag_name_to_param_name(tier, tag_name).
        # For example: a tag called 'spa-env-file' and a stack parameter called 'spaEnvFile'.
        # So the map() with the lambda function creates a list of Tag objects such as
        # Tag('env-file', Ref('spaEnvFile', True). Additionally, add the lh-app and lh-app-env tags.
        Tags=list(map(lambda tag_name: Tag(tag_name, Ref(tag_name_to_param_name(tier, tag_name)), True), tags)) \
             + [Tag('lh-app', Ref('lhAppTag'), True), Tag('lh-app-env', Ref('lhAppEnvTag'), True)]
    ))

    spec = PredefinedMetricSpecification(PredefinedMetricType="ASGAverageCPUUtilization")
    config = TargetTrackingConfiguration(PredefinedMetricSpecification=spec,
                                         TargetValue=50.0,
                                         DisableScaleIn="True")

    t.add_resource(ScalingPolicy(
        tier + "ScalingPolicy",
        PolicyType="TargetTrackingScaling",
        TargetTrackingConfiguration=config,
        AutoScalingGroupName=Ref(asg)
    ))

    return asg
