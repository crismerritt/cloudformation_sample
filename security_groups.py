from troposphere import Ref, GetAtt
from troposphere.ec2 import SecurityGroup, SecurityGroupRule


# The security group model is as follows:
# - The load-balancer is in a SG that allows HTTP and HTTPS from anywhere.
# - EC2 instances in the SPA, admin and API autoscaling groups are in respective SGs that allow HTTP from the ALB.
# - API instances are additionally in the existing DatabaseSG - see the comment in main().

def __make_alb_security_group(t):
    sg = t.add_resource(SecurityGroup(
        "albSG",
        GroupDescription='Enable HTTP and HTTPS from everywhere',
        VpcId=Ref('VPC'),
        SecurityGroupIngress=[
            SecurityGroupRule(
                IpProtocol="tcp",
                FromPort="80",
                ToPort="80",
                CidrIp="0.0.0.0/0"
            ),
            SecurityGroupRule(
                IpProtocol="tcp",
                FromPort="443",
                ToPort="443",
                CidrIp="0.0.0.0/0"
            )
        ],
        Tags=[
            {'Key': 'lh-app', 'Value': Ref('lhAppTag')},
            {'Key': 'lh-app-env', 'Value': Ref('lhAppEnvTag')}
        ]
    ))

    return sg


# make a security group for the EC2 instances in the SPA, API or admin tiers
# these instances are reachable from the ALB on port 80
def __make_ec2_security_group(t, tier, alb_sg):
    sg = t.add_resource(SecurityGroup(
        tier + "SG",
        GroupDescription='Enable HTTP from ALB and SSH from everywhere',
        VpcId=Ref('VPC'),
        SecurityGroupIngress=[
            SecurityGroupRule(
                IpProtocol="tcp",
                FromPort="80",
                ToPort="80",
                SourceSecurityGroupId=GetAtt(alb_sg, "GroupId")
            ),

            # Note: I have chosen to allow SSH from anywhere into the SPA, API and admin instances.
            # This is because we regularly need to log into those hosts to debug stuff on the app and
            # I consider the SSH keys and the way we manage them to be strong. For higher security, get
            # rid of the SSH access here and force folks to manually add a stand-alone SSH security group
            # to an instance if they need to log in.
            SecurityGroupRule(
                IpProtocol="tcp",
                FromPort="22",
                ToPort="22",
                CidrIp="0.0.0.0/0"
            )
        ],
        Tags=[
            {'Key': 'lh-app', 'Value': Ref('lhAppTag')},
            {'Key': 'lh-app-env', 'Value': Ref('lhAppEnvTag')}
        ]
    ))

    return sg


def make_security_groups(t):
    alb_sg = __make_alb_security_group(t)
    spa_sg = __make_ec2_security_group(t, 'spa', alb_sg)
    api_sg = __make_ec2_security_group(t, 'api', alb_sg)
    admin_sg = __make_ec2_security_group(t, 'admin', alb_sg)
    return {'alb': alb_sg, 'spa': spa_sg, 'api': api_sg, 'admin': admin_sg}
