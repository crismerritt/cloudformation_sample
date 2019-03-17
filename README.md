# Overview
This directory contains code that generates 2 CloudFormations templates. 
Running the generated CF templates creates the following:

1. A new VPC with a 3 public subnets, route table and internet gateway
2. A load-balancer and auto-scaling configuration that launches EC2 intances in the in the VPC.

We use Troposhpere to generate the CF templates. Troposhpere is a Python library
that wraps CloudFormation. See https://github.com/cloudtools/troposphere.

# Quickstart

1. Tested with Python 3.7.
2. Install Python dependencies: **troposhpere** and **awacs**.
3. Run **python make_vpc.py > vpc.json** to generate VPC CF template.
4. Run **python make_app_cluster.py > app_cluster.json** to generate the app-cluster CF template.
5. Using CF, deploy first the VPC, then deploy the app-cluster into the VPC.


# Files

* **make_vpc.py** generates the VPC template. It is self-contained.
* **make_app_cluster.py** is the main entry point to generate the app-cluster CF template. Start reading here.
* The following files support make_app_cluster.py:
  * **autoscaling_group.py** - creates autoscaling groups and launch configurations
  * **load_balancer.py** - creates a load balancer
  * **security_groups.py** - documents and implements the security group model
  * **iam.py** - creates an instance profile; it goes in the launch configuration
  * **utils.py** - little one-liner utilities
  * **user_data_api/spa.sh** - user-data scripts for the launch configurations.