from troposphere import Ref
from troposphere.iam import Role, InstanceProfile
from troposphere.iam import PolicyType as IAMPolicy
from awacs.aws import Allow, Statement, Principal, Policy, Action
from awacs.sts import AssumeRole


def make_instance_profile(t):
    role = t.add_resource(Role(
        "EC2Role",
        AssumeRolePolicyDocument=Policy(
            Statement=[
                Statement(
                    Effect=Allow,
                    Action=[AssumeRole],
                    Principal=Principal("Service", ["ec2.amazonaws.com"])
                )
            ]
        )
    ))

    t.add_resource(IAMPolicy(
        "DescribeTagsPolicy",
        PolicyName="DescribeTagsPolicy",
        PolicyDocument=Policy(
            Statement=[
                Statement(
                    Effect=Allow,
                    Action=[Action("ec2", "DescribeTags")],
                    Resource=["*"]
                )
            ]
        ),
        Roles=[Ref(role)]
    ))

    profile = t.add_resource(InstanceProfile(
        "InstanceProfile",
        Roles=[Ref(role)]
    ))

    return profile
