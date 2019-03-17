#!/usr/bin/env bash

repo_dir=/home/ubuntu/refapp-repo
deploy_dir=/var/www/refapp

# See https://gist.github.com/codeinthehole/ab9a8dc30917c5705846
#
# Note the instance needs to have an IAM role that lets it read tags. The policy
# JSON for this looks like:
#
#    {
#      "Version": "2012-10-17",
#      "Statement": [
#        {
#          "Effect": "Allow",
#          "Action": "ec2:DescribeTags",
#          "Resource": "*"
#        }
#      ]
#    }
#

# Grab the instance ID and region as the 'describe-tags' action below requires them. 
# See http://stackoverflow.com/questions/4249488/find-region-from-within-ec2-instance.
INSTANCE_ID=$(ec2metadata --instance-id)
REGION=$(curl -s http://169.254.169.254/latest/dynamic/instance-identity/document | grep region | awk -F\" '{print $4}')

# AWS CLI is here
PATH=$PATH:/usr/local/bin

get_tag() {
	tag=$1
	aws ec2 describe-tags --filters "Name=resource-id,Values=$INSTANCE_ID" "Name=key,Values=$tag" --region=$REGION --output=text | cut -f5
}

error() {
	echo error $*
	exit 1
}

# autoredeploy cron-job calls this script with the argument 'autoredeploy'
if [ "$1" == 'autoredeploy' ]; then
	# if the autoredeploy tag is not set by the autoscaling group, or set to false, exit now
	autoredeploy_tag=$(get_tag autoredeploy)
	[[ -z "$autoredeploy_tag" || "$autoredeploy_tag" == "false" ]] && exit 0
fi

# at launch time, there is apparently a race condition on the autoscaling group propogating tags to the instance. 
# tags for the instance may take a few seconds to become visible through the 'aws ec2 describe-tags' api call. 
# it's a bit ugly, but sleeping 10 seconds seems to be a reliable work around.
sleep 10

# read the values of the following tags, which are set in the autoscaling group and propogated
# to instances when they are launched: repo-url, repo-branch, env-file
repo_url=$(get_tag repo-url); [ -z "$repo_url" ] && error getting repo-url tag
repo_branch=$(get_tag repo-branch); [ -z "$repo_branch" ] && error getting repo-branch tag
env_file=$(get_tag env-file); [ -z "$env_file" ] && error getting env-file tag

# create deploy dir owned by ubuntu user
if [ ! -e $deploy_dir ]; then
	mkdir -p $deploy_dir && chown ubuntu:ubuntu $deploy_dir
fi

# run this portion as the ubuntu user
su - ubuntu << EOF

error() {
	echo error $*
	exit 1
}

if [ ! -d $repo_dir ]; then
	mkdir -p $repo_dir || error creating $repo_dir
	echo cloning git repo
	git clone $repo_url $repo_dir || error cloning git repo $repo_url
fi

cd $repo_dir || error changing to $repo_dir
git checkout $repo_branch || error switching git repo to branch $repo_branch
git pull || error pulling repo changes

echo setting npm build env-vars from $env_file
ln -sf $env_file .env || error creating link to $env_file
source .env || error sourcing $env_file

echo running npm install
npm install || error running npm install

echo running npm build
npm run build || error running npm run build

# look for a file called refapp-crontab. if it exists, load it into the ubuntu user's crontab
if [[ -r refapp.cron ]]; then
	echo loading refapp.cron
	crontab refapp.cron || error loading refapp.cron
fi

EOF

# now we are root again
(($?)) && exit 1

error() {
	echo error $*
	exit 1
}

echo delete old directory of webapp
rm -rf $deploy_dir || error deleting $deploy_dir

echo copy new version of web app into web root
mv $repo_dir/dist $deploy_dir || error moving distribution files to $deploy_dir

echo make www-data owner of $deploy_dir
chown -R www-data:www-data $deploy_dir

echo restart nginx
/usr/sbin/service nginx restart || error restarting nginx

# install autoredeploy cron job as root
cron_job='*/10 * * * * bash /var/lib/cloud/instance/user-data.txt autoredeploy >> /var/log/cloud-init-output.log 2>&1'
echo "$cron_job" | crontab -u root -

echo deploy sucessful
exit 0
