from troposphere import Template, Parameter, Ref, GetAZs, Select
from troposphere.ec2 import VPC, Subnet, InternetGateway, VPCGatewayAttachment, RouteTable, Route, \
    SubnetRouteTableAssociation

VPC_CIDRBLOCK = "10.0.0.0/16"
SUBNET_A_CIDRBLOCK = "10.0.1.0/24"
SUBNET_B_CIDRBLOCK = "10.0.2.0/24"
SUBNET_C_CIDRBLOCK = "10.0.3.0/24"


def add_parameters(t):
    t.add_parameter(Parameter(
        "vpcName",
        Type="String",
        Description="Name for this VPC",
        Default="MyVPC"
    ))

    t.add_parameter(Parameter(
        "lhAppTag",
        Type="String",
        Description="lh-app tag for this VPC",
        Default="my-app"
    ))

    t.add_parameter(Parameter(
        "lhAppEnvTag",
        Type="String",
        Description="lh-app-env tag for this VPC",
        Default="prod"
    ))


def __make_subnet(t, vpc, route_table, subnet_name, cidr_block):
    subnet = t.add_resource(Subnet(
        subnet_name,
        VpcId=Ref(vpc),
        CidrBlock=cidr_block,
        AvailabilityZone=Select(0, GetAZs(Ref("AWS::Region"))),
        Tags=[
            {'Key': 'lh-app', 'Value': Ref('lhAppTag')},
            {'Key': 'lh-app-env', 'Value': Ref('lhAppEnvTag')},
        ]
    ))

    t.add_resource(SubnetRouteTableAssociation(
        subnet_name+'RouteTableAssociation',
        SubnetId=Ref(subnet),
        RouteTableId=Ref(route_table)
    ))


# create a VPC with 3 public subnets, route-table and internet gateway
def make_vpc(t):
    vpc = t.add_resource(VPC(
        "VPC",
        CidrBlock=VPC_CIDRBLOCK,
        Tags=[
            {'Key': 'lh-app', 'Value': Ref('lhAppTag')},
            {'Key': 'lh-app-env', 'Value': Ref('lhAppEnvTag')},
        ]
    ))

    igw = t.add_resource(InternetGateway(
        "InternetGateway",
        Tags=[
            {'Key': 'lh-app', 'Value': Ref('lhAppTag')},
            {'Key': 'lh-app-env', 'Value': Ref('lhAppEnvTag')},
        ]
    ))

    igw_attachment = t.add_resource(VPCGatewayAttachment(
        "GatewayAttachment",
        VpcId=Ref(vpc),
        InternetGatewayId=Ref(igw)
    ))

    route_table = t.add_resource(RouteTable(
        "PublicRouteTable",
        VpcId=Ref(vpc),
        Tags=[
            {'Key': 'lh-app', 'Value': Ref('lhAppTag')},
            {'Key': 'lh-app-env', 'Value': Ref('lhAppEnvTag')},
        ]
    ))

    t.add_resource(Route(
        'RouteToInternet',
        GatewayId=Ref(igw),
        DestinationCidrBlock='0.0.0.0/0',
        RouteTableId=Ref(route_table),
        DependsOn=igw_attachment.title
    ))

    __make_subnet(t, vpc, route_table, "SubnetA", SUBNET_A_CIDRBLOCK)
    __make_subnet(t, vpc, route_table, "SubnetB", SUBNET_B_CIDRBLOCK)
    __make_subnet(t, vpc, route_table, "SubnetC", SUBNET_C_CIDRBLOCK)


def main():
    t = Template()
    t.add_version("2010-09-09")
    t.add_description("Create a VPC with 3 public subnets")
    add_parameters(t)
    make_vpc(t)
    print(t.to_json())


if __name__ == '__main__':
    main()
